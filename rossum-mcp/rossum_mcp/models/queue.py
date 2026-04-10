"""Queue-related models and enums."""

from __future__ import annotations

from enum import StrEnum


class AutomationLevel(StrEnum):
    NEVER = "never"
    ALWAYS = "always"
    CONFIDENT = "confident"


class QueueLocale(StrEnum):
    AUTO = "auto"
    EN_US = "en_US"
    EN_GB = "en_GB"
    DE_DE = "de_DE"
    DE_AT = "de_AT"
    DE_CH = "de_CH"
    FR_FR = "fr_FR"
    FR_BE = "fr_BE"
    FR_CH = "fr_CH"
    CS_CZ = "cs_CZ"
    SK_SK = "sk_SK"
    ES_ES = "es_ES"
    IT_IT = "it_IT"
    PT_PT = "pt_PT"
    PT_BR = "pt_BR"
    NL_NL = "nl_NL"
    NL_BE = "nl_BE"
    PL_PL = "pl_PL"
    HU_HU = "hu_HU"
    RO_RO = "ro_RO"
    JA_JP = "ja_JP"
    ZH_CN = "zh_CN"
    KO_KR = "ko_KR"
    DA_DK = "da_DK"
    FI_FI = "fi_FI"
    SV_SE = "sv_SE"
    NB_NO = "nb_NO"


class QueueTemplateName(StrEnum):
    EU_DEMO = "EU Demo Template"
    APR_EU_DEMO = "AP&R EU Demo Template"
    TAX_INVOICE_EU_DEMO = "Tax Invoice EU Demo Template"
    US_DEMO = "US Demo Template"
    APR_US_DEMO = "AP&R US Demo Template"
    TAX_INVOICE_US_DEMO = "Tax Invoice US Demo Template"
    UK_DEMO = "UK Demo Template"
    APR_UK_DEMO = "AP&R UK Demo Template"
    TAX_INVOICE_UK_DEMO = "Tax Invoice UK Demo Template"
    CZ_DEMO = "CZ Demo Template"
    EMPTY_ORGANIZATION = "Empty Organization Template"
    DELIVERY_NOTES_DEMO = "Delivery Notes Demo Template"
    DELIVERY_NOTE_DEMO = "Delivery Note Demo Template"
    CHINESE_INVOICES_FAPIAO_DEMO = "Chinese Invoices (Fapiao) Demo Template"
    TAX_INVOICE_CN_DEMO = "Tax Invoice CN Demo Template"
    CERTIFICATES_OF_ANALYSIS_DEMO = "Certificates of Analysis Demo Template"
    PURCHASE_ORDER_DEMO = "Purchase Order Demo Template"
    CREDIT_NOTE_DEMO = "Credit Note Demo Template"
    DEBIT_NOTE_DEMO = "Debit Note Demo Template"
    PROFORMA_INVOICE_DEMO = "Proforma Invoice Demo Template"


QUEUE_TEMPLATE_NAMES = tuple(QueueTemplateName)
