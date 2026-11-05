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
| Status        | ✅ Licence cleared. Feature selection decided (see below). Downloaded to `data/raw/phishing_mendeley/dataset_small.csv` (16,028,060 bytes, SHA-256 verified). |

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
| Notes         | The CIC page now says "We apologize, this dataset is no longer available", so files cannot be downloaded from the official page. The terms text on that page (read 2026-11-05) allows redistribution and mirroring with a citation. Attacks date from 1999 traffic. |
| Candidate copy | Zenodo record 17424143, "NSL-KDD Dataset", uploaded by Saad (Helwan University), published 2025-10-23. Files: `KDDTrain+.txt` (14,738,831 bytes, md5 `120b13c9092ab72d4902f2079143cc2c`) and `KDDTest+.txt` (2,573,994 bytes, md5 `1e53a506c102628114ca1b1fa509b6a8`). Record licence CC BY 4.0. The record does not name the original source or the original terms. |
| Downloaded (2026-11-05) | Saved to `data/raw/nsl_kdd/` (not committed). Sizes and md5 match the Zenodo listing. |
| Check results | **`KDDTrain+.txt`:** 125,973 rows, 43 tab-separated columns (41 features, label, difficulty), no missing values. The label counts match the known split: 67,343 normal and 58,630 attack records. **`KDDTest+.txt`:** 22,544 rows, 42 columns, no missing values. Its label column has only two values, `Normal` (9,711) and `Attack` (12,833). The NSL-KDD test set is usually described as having named attack types in its label column, so this file may be a relabelled or altered copy. |
| Second copy found (2026-11-05) | GitHub repository `jmnwong/NSL-KDD-Dataset`: `KDDTest+.txt` (3,441,513 bytes, git blob SHA `b30e89605285a5ccd8cf8fd38dba72906c20d3dd`) and `KDDTrain+.txt` (19,109,424 bytes). Sizes differ from the Zenodo files (2,573,994 and 14,738,831 bytes), so the two are **not** byte-identical. The repository licence was not returned by the GitHub API, so it is unconfirmed. Not downloaded. |
| Comparison result (2026-11-05) | The GitHub `KDDTest+.txt` was downloaded to `data/raw/nsl_kdd_reference/` (not committed). Its git blob SHA-1 matches GitHub's record, and it has 22,544 rows and 43 columns, with 38 distinct labels and difficulty levels. Comparing it with the Zenodo test file: (a) the 41 numeric features and the protocol and flag columns match, (b) the Zenodo label column is the binary form of the GitHub label (`normal` becomes `Normal`, every attack becomes `Attack`, with 0 mismatches), and the difficulty column is dropped, (c) **306 rows differ in the service column**: GitHub says `imap4` where Zenodo says `Attack4`. This means the Zenodo test file is **altered** and must not be used. |
| Training file comparison (2026-11-05) | GitHub `KDDTrain+.txt` downloaded to `data/raw/nsl_kdd_reference/` (not committed). Its git blob SHA-1 matches GitHub's record (19,109,424 bytes). Compared with the Zenodo training file: same row count (125,973), same 67,343 normal records, and every value identical. |
| Checks still needed | (1) Confirm the licence of the GitHub repository (the API returned none). (2) Team approval to use either file. (3) Cite Tavallaee et al. (2009) and the CIC terms in the report. |
| Status        | ❌ Zenodo test file **rejected** (altered service values in 306 rows and relabelled). Zenodo training file **matches the GitHub training file value for value**: 125,973 rows, identical labels and difficulty, and every numeric and text value equal. The only differences are in file format (Zenodo uses tabs, GitHub uses commas). Use it only after the GitHub repository's licence is confirmed and the team approves it. |

### Feature decision for the Mendeley URL dataset (2026-11-05)

The file was downloaded from the official Mendeley API link, and its SHA-256
checksum matches the value Mendeley publishes. The small variant has 58,645 rows
and 111 feature columns plus the label `phishing`. All checks below were run on
that file.

Rule (ADR-0007): the phone may use only features computed from the URL string.
Any feature that needs DNS, WHOIS, a TLS connection, a page fetch, or a search
engine lookup is dropped.

| Group | Columns | Count | Decision |
|---|---|---|---|
| URL-string counts and lengths (`qty_*_url`, `length_url`) | 0–18 | 19 | Keep |
| Domain-string counts (`qty_*_domain`, `domain_length`, `qty_vowels_domain`) | 19–37 | 19 | Keep, except the 13 constant columns below |
| IP-in-host and server/client word check (`domain_in_ip`, `server_client_domain`) | 38–39 | 2 | Keep |
| Path counts and lengths (`qty_*_directory`, `directory_length`) | 40–57 | 18 | Keep |
| File-name counts and lengths (`qty_*_file`, `file_length`) | 58–75 | 18 | Keep |
| Parameter counts and lengths (`qty_*_params`, `params_length`, `qty_params`, `tld_present_params`) | 76–95 | 20 | Keep |
| Email in URL (`email_in_url`) | 96 | 1 | Keep |
| URL shortener check (`url_shortened`) | 110 | 1 | Keep, if the shortener list is bundled with the app |
| **Network or web lookups** | 97–109 | 13 | **Drop** |

**Dropped (need network or web lookups):** `time_response`, `domain_spf`,
`asn_ip`, `time_domain_activation`, `time_domain_expiration`,
`qty_ip_resolved`, `qty_nameservers`, `qty_mx_servers`, `ttl_hostname`,
`tls_ssl_certificate`, `qty_redirects`, `url_google_index`,
`domain_google_index`.

**Dropped (constant, no information):** `qty_slash_domain`,
`qty_questionmark_domain`, `qty_equal_domain`, `qty_and_domain`,
`qty_exclamation_domain`, `qty_space_domain`, `qty_tilde_domain`,
`qty_comma_domain`, `qty_plus_domain`, `qty_asterisk_domain`,
`qty_hashtag_domain`, `qty_dollar_domain`, `qty_percent_domain`. Each has only
one value in the file.

**Result:** 111 features reduce to **85 usable URL-string features**. The
training code will build this list from the rule above, and the phone code
will use the same list. Both must be kept in step.

**Note:** `qty_at_domain` takes 2 values, so it is kept. Its variance is
very low and it should be checked during feature selection.

---

## Summary

| Threat | Dataset | Licence | Status |
|---|---|---|---|
| SMS | UCI SMS Spam Collection | CC BY 4.0 | ✅ Cleared |
| URL | Phishing Websites Dataset (Mendeley) | CC BY 4.0 | ⚠️ Feature list open |
| Network | NSL-KDD | Redistribution allowed with citation | ❌ Official download unavailable |
