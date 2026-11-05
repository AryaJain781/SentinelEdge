# Data Sources

Track every dataset the project uses here. **Datasets themselves are never
committed** (see `.gitignore`: `data/raw/`, `data/processed/`, `*.csv`,
`*.parquet`). Only the description and the download instructions go in
this file.

Licence checks below were done on the official pages on 2026-11-05.

## Template (copy for each dataset)

| Field         | Entry                                              |
|---------------|----------------------------------------------------|
| Name          | _name_                                             |
| Source / URL  | _official page_                                    |
| Licence       | _as stated on the official page, with the date checked_ |
| Version / date| _version or download date_                         |
| Size          | _rows x columns, disk size_                        |
| Labels        | _attack classes and how they were labelled_        |
| Local path    | `data/raw/<name>/` (not committed)                 |
| Used in phase | _Phase number_                                     |
| Notes         | _pre-processing, known issues_                     |

## Registered datasets

### 1. SMS spam: UCI SMS Spam Collection

| Field         | Entry |
|---------------|-------|
| Source / URL  | https://archive.ics.uci.edu/dataset/228/sms+spam+collection |
| Licence       | **CC BY 4.0** (confirmed on the UCI page, 2026-11-05). Attribution required. |
| Citation      | Almeida, T. and Hidalgo, J. (2011). SMS Spam Collection. UCI Machine Learning Repository. https://doi.org/10.24432/C5CC84 |
| Size          | 5,574 messages: 747 spam, 4,827 ham (sums confirmed from the page's source breakdown) |
| Labels        | spam / ham (given by the dataset) |
| Local path    | `data/raw/sms_uci/` (not committed) |
| Used in phase | Phase 2 onward (SMS detector, WP3) |
| Notes         | English only. Message text only, no sender information. |
| Status        | ✅ Cleared for use |

### 2. Phishing URLs: Phishing Websites Dataset (Vrbančič, Fister Jr., Podgorelec)

| Field         | Entry |
|---------------|-------|
| Source / URL  | https://data.mendeley.com/datasets/72ptz43s9v/1 |
| Licence       | **CC BY 4.0** (confirmed on the Mendeley record, 2026-11-05). Attribution required. |
| Citation      | Vrbančič, G., Fister Jr., I. and Podgorelec, V. (2020). *Data in Brief*, 33, 106438. https://doi.org/10.1016/j.dib.2020.106438 |
| Size          | Small variant: 58,645 rows (27,998 legitimate, 30,647 phishing). Full variant: 88,647 rows (58,000 legitimate, 30,647 phishing). 111 features per variant. |
| Labels        | 0 = legitimate, 1 = phishing |
| Local path    | `data/raw/phishing_mendeley/` (not committed) |
| Used in phase | Phase 2 onward (URL detector, WP2) |
| Notes         | **Open item:** the Mendeley page does not list the 111 feature names or say which features come from the URL string alone and which come from the web page. The phone can only use URL-string features (ADR-0007). The column list must be built from the downloaded CSV and its documentation before training. |
| Status        | ⚠️ Licence cleared. Feature selection still open. |

### 3. Network flows: NSL-KDD (Canadian Institute for Cybersecurity, UNB)

| Field         | Entry |
|---------------|-------|
| Source / URL  | https://www.unb.ca/cic/datasets/nsl.html |
| Licence       | Redistribution and mirroring allowed, with citation required (stated on the CIC page, 2026-11-05). |
| Citation      | Tavallaee, M., Bagheri, E., Lu, W. and Ghorbani, A. A. (2009). "A Detailed Analysis of the KDD CUP 99 Data Set." *IEEE CISDA 2009*. |
| Size          | Not stated on the CIC page. Commonly quoted: KDDTrain+ about 125,000 records, KDDTest+ 22,544 records. Confirm after download. |
| Labels        | Normal or attack type, with 41 features per record |
| Local path    | `data/raw/nsl_kdd/` (not committed) |
| Used in phase | Phase 2 onward (network detector, WP4) |
| Notes         | **Open item:** the CIC page now says "We apologize, this dataset is no longer available." Files cannot be downloaded from the official page. Any mirror must be checked for the same licence and file integrity before use. Attacks date from 1999 traffic. |
| Status        | ❌ Blocked until a working copy is found and checked |

---

## Summary

| Threat | Dataset | Licence | Status |
|---|---|---|---|
| SMS | UCI SMS Spam Collection | CC BY 4.0 | ✅ Cleared |
| URL | Phishing Websites Dataset (Mendeley) | CC BY 4.0 | ⚠️ Feature list open |
| Network | NSL-KDD | Redistribution allowed with citation | ❌ Official download unavailable |
