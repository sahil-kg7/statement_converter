from __future__ import annotations

from pathlib import Path

from app.csv_adapters.base import CsvParseContext
from app.csv_adapters.canara_savings import CanaraSavingsCsvParser
from app.csv_adapters.generic import GenericCsvParser
from app.parsers.base import BankName, PdfBankParser, StatementKind
from app.parsers.banks.hdfc_creditcard import HdfcCreditCardPdfParser
from app.parsers.banks.hdfc_savings import HdfcSavingsPdfParser
from app.parsers.banks.hdfc_savings_v2 import HdfcSavingsPdfParserV2
from app.parsers.banks.kotak_creditcard import KotakCreditCardPdfParser
from app.parsers.banks.kotak_savings import KotakSavingsPdfParser
from app.parsers.banks.kotak_savings_v2 import KotakSavingsPdfParserV2
from app.parsers.detector import detect_pdf_statement
from app.parsers.text_extractor import extract_pdf_text
from app.pipeline.fallback import run_fallback_chain
from app.pipeline.ingest import InputKind, sniff_input_kind
from app.pipeline.models import ConversionResult
from app.config import settings


class ConversionOrchestrator:
    def __init__(self) -> None:
        self.csv_parsers = [CanaraSavingsCsvParser(), GenericCsvParser()]
        self.pdf_parsers: dict[tuple[BankName, StatementKind], list[PdfBankParser]] = {
            (BankName.HDFC, StatementKind.SAVINGS): [
                HdfcSavingsPdfParserV2(),
                HdfcSavingsPdfParser(),
            ],
            (BankName.HDFC, StatementKind.CREDIT_CARD): [HdfcCreditCardPdfParser()],
            (BankName.KOTAK, StatementKind.SAVINGS): [
                KotakSavingsPdfParserV2(),
                KotakSavingsPdfParser(),
            ],
            (BankName.KOTAK, StatementKind.CREDIT_CARD): [KotakCreditCardPdfParser()],
        }

    def convert(self, file_name: str, payload: bytes) -> ConversionResult:
        input_kind = sniff_input_kind(file_name, payload)

        if input_kind is InputKind.PDF:
            extracted = extract_pdf_text(payload)
            detection = detect_pdf_statement(extracted.text)
            detected_bank = detection.bank.value if detection is not None else None
            detected_kind = (
                detection.statement_kind.value if detection is not None else None
            )
            adapter_layer = (
                f"adapter:{detected_bank}:{detected_kind}"
                if detection is not None
                else "adapter:unmatched"
            )

            if detection is not None:
                parser_list = self.pdf_parsers.get(
                    (detection.bank, detection.statement_kind), []
                )
                if parser_list:
                    for parser in parser_list:
                        try:
                            transactions = parser.parse(extracted.text)
                            if len(transactions) >= max(1, settings.min_rows_threshold):
                                return ConversionResult(
                                    transactions=transactions,
                                    detected_bank=detected_bank,
                                    statement_kind=detected_kind,
                                    conversion_source="adapter",
                                )
                        except ValueError:
                            continue
                else:
                    adapter_layer = (
                        f"adapter:{detected_bank}:{detected_kind}:unimplemented"
                    )

            fallback_result = run_fallback_chain(
                payload,
                extracted.text,
                detected_bank=detected_bank,
                detected_kind=detected_kind,
                layers_tried=[adapter_layer],
            )
            return ConversionResult(
                transactions=fallback_result.transactions,
                detected_bank=fallback_result.detected_bank,
                statement_kind=fallback_result.detected_kind,
                conversion_source="fallback",
            )

        raw_text = self._decode_text_payload(payload)
        for parser in self.csv_parsers:
            if parser.matches(raw_text):
                transactions = parser.parse(
                    raw_text, CsvParseContext(source_path=Path(file_name))
                )
                return ConversionResult(
                    transactions=transactions, conversion_source="csv"
                )

        raise ValueError("Unable to parse the uploaded CSV")

    @staticmethod
    def _decode_text_payload(payload: bytes) -> str:
        for encoding in ("utf-8", "cp1252", "latin-1"):
            try:
                return payload.decode(encoding)
            except UnicodeDecodeError:
                continue
        raise ValueError("Could not decode the uploaded text file")
