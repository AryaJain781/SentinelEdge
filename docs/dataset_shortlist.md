# Dataset Shortlist (Phase 1)

We need one public research dataset for each of our three threat types. This
shortlist records what each dataset contains, its licence status, and any
limitations. **No dataset has been downloaded yet.** Before any dataset is
used in code, its licence must be confirmed on the official page, as
recorded in the table below.

**Licence status key:**
- ✅ **Confirmed:** the official page states the licence.
- ⚠️ **Verify:** sources disagree or the licence field is empty. Check the
  official page before use.

---

## 1. SMS: UCI SMS Spam Collection

| Field | Details |
|---|---|
| Purpose | Scam and spam SMS detection (text messages labelled spam or ham) |
| Sample count | 5,574 English SMS messages. About 13% are spam (747 spam, 4,827 ham). |
| Format | Plain text, one message per line, with a label |
| Official page | https://archive.ics.uci.edu/dataset/228 |
| Licence | ⚠️ **Verify.** You asked us to record CC BY 4.0. Our search could not confirm that from the UCI page. Other copies list "no known license" or CC BY-SA 4.0. Check the licence section on the UCI page before use. |
| Citation | Almeida, T. and Hidalgo, J. (2011). SMS Spam Collection. UCI Machine Learning Repository. https://doi.org/10.24432/C5CC84 |
| Limitations | English only. Messages are older. No sender information, so sender features cannot be trained. |

---

## 2. URLs: Phishing Websites Dataset (Vrbančič, Fister Jr. and Podgorelec)

| Field | Details |
|---|---|
| Purpose | Phishing and legitimate website classification |
| Sample count | 58,645 instances in the smaller version (27,998 legitimate and 30,647 phishing). A larger version has 88,647 instances. |
| Format | Tabular features (CSV) with a label column |
| Official page | https://data.mendeley.com/datasets/72ptz43s9v |
| Companion paper | Vrbančič, G., Fister Jr., I. and Podgorelec, V. (2020). *Data in Brief*, 33, 106438. https://doi.org/10.1016/j.dib.2020.106438 |
| Licence | ⚠️ **Verify.** The Mendeley licence field showed no value in our search. The associated GitHub repository metadata lists **MIT**. Confirm on the Mendeley record before use. |
| Citation | Cite the Data in Brief paper above. |
| Limitations | **Check the feature list.** Some features in this family of datasets come from the web page content (HTML). At runtime our phone detector may use only features computed from the URL string, so we must select those columns and drop the page-content ones. |

**Why not the other two URL sources?**

- **PhishTank:** we found that its terms are restrictive and we could not confirm
  the exact conditions. It is also a live feed of reported links, not a
  fixed benchmark, which makes results hard to reproduce. Not selected.
- **Tranco:** a ranking of popular domains. It is useful as a source of
  **benign** domains, to pair with the phishing list. We did not verify its
  licence in this phase. Treat it as an optional supplement that must be
  checked before use.

---

## 3. Network flows: NSL-KDD

| Field | Details |
|---|---|
| Purpose | Intrusion detection (normal traffic and attack types such as scans and floods) |
| Sample count | KDDTrain+ training file: about 125,000 records (commonly quoted as 125,973). KDDTest+ test file: 22,544 records. Sources differ slightly, so we will state the exact count after download. |
| Features | 41 features per connection, plus a label and difficulty level |
| Official page | https://www.unb.ca/cic/datasets/nsl.html (Canadian Institute for Cybersecurity, University of New Brunswick). Confirm the URL before use. |
| Licence | ⚠️ **Verify.** Our search did not find licence terms. The dataset is widely described as free for research. Check the CIC page for the exact terms. |
| Citation | Tavallaee, M., Bagheri, E., Lu, W. and Ghorbani, A. A. (2009). "A Detailed Analysis of the KDD CUP 99 Data Set." *IEEE CISDA 2009*. |
| Limitations | Based on 1999 network traffic, so its attacks are old. Its features are already computed, so we cannot train on raw packets from this dataset. The report must state this. |

---

## Summary

| Threat | Dataset | Records | Licence status | Main limitation |
|---|---|---|---|---|
| SMS scam | UCI SMS Spam Collection | 5,574 messages | ⚠️ Verify | English, older, no sender data |
| Phishing URL | Phishing Websites Dataset (Mendeley) | 58,645 (small version) | ⚠️ Verify (MIT on GitHub) | Select URL-only features |
| Network intrusion | NSL-KDD | About 125k train, 22,544 test | ⚠️ Verify | 1999 traffic |

**Next step before Phase 2:** confirm each licence on its official page, record
the result in `docs/data_sources.md`, and set the URL-feature column list for
the Mendeley dataset.
