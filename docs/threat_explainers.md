# Threat Explainers (Phase 1)

This document explains the three threat types the project targets, in plain
language. For each one it lists the clues (features) we can extract **offline,
on the phone, without any network call**, and the trade-off between false
positives and false negatives.

**Key terms**

- **False positive (FP):** a safe item wrongly flagged as a threat. The user is
  annoyed or blocked for no reason.
- **False negative (FN):** a real threat that is missed. The user is exposed.
- **Precision:** of everything flagged, how much was really a threat.
- **Recall:** of all real threats, how many we caught.
- **Threshold:** the score above which we raise an alert. Lowering it catches
  more threats (higher recall) but causes more false alarms (lower precision).

All features below are **static features**: they can be computed from the
item itself (a URL string, an SMS text, a network flow record) without
visiting the link or contacting any server. This is what keeps the system
offline and safe.

---

## a) Phishing URLs

A phishing URL tries to look like a trusted website so that the user types
in a password or card number. The attacker's main tools are disguise and
misdirection.

### How the attack works in plain words

- **Typosquatting:** a near-copy of a real name, such as `paypa1.com`
  (digit 1 instead of letter l) or `amazonn-help.com`.
- **Homoglyphs:** letters from another alphabet that look identical, such as
  a Cyrillic "а" in place of a Latin "a". The domain looks right to the eye but
  is a different name. Such names are often stored as Punycode, which starts
  with `xn--`.
- **Subdomain masking:** the real domain is hidden at the end, and a trusted
  name is put at the front, such as `secure.bank.example.account-check.ru`.
  Only the last two parts (`account-check.ru`) identify the real owner.
- **Suspicious TLDs (top-level domains):** endings such as `.zip`, `.top`,
  `.xyz` or `.tk` are cheap or free and are used often by attackers. They are
  also used by many legitimate sites, so they are a clue, not proof.
- **High entropy:** random-looking strings such as `x7kq2-pl9mz.com` have high
  entropy (they are hard to predict). Real brand names are readable.
- **Other clues:** many hyphens, very long URLs, an IP address in place of a
  name, an `@` sign that hides the real destination, and login words such as
  "verify", "secure", "update" or "account".

### Static features we extract offline

| Feature | Example | Why it helps |
|---|---|---|
| URL length, count of dots, hyphens, digits | `a-b-c-1234.com` | Phishing URLs are often long or cluttered |
| Has IP address as host | `http://192.168.4.7/login` | Real banks rarely use raw IPs |
| TLD class | `.zip`, `.top` | Cheap or free TLDs are over-represented |
| Subdomain depth | `a.b.c.d.example.com` | Deep nesting hides the real owner |
| Non-ASCII or `xn--` characters | `xn--pypal-4ve.com` | Homoglyph disguise |
| Shannon entropy of the domain | high value = random | Generated domains are random-looking |
| Edit distance to known brands | `paypa1` vs `paypal` = 1 edit | Typosquatting detection |
| Login keywords present | `verify`, `secure`, `login` | Phishing pages use urgent words |
| `@` symbol in the URL | `http://bank.com@evil.com` | The browser goes to the part after `@` |

### False positive vs. false negative trade-off

- **False positive:** a real bank or small business with an unusual domain or a
  new `.xyz` address is blocked. The cost is a frustrated user and lost trust.
- **False negative:** a freshly registered phishing domain with clean-looking
  features is allowed. The cost can be stolen credentials, which is serious.
- **Our stance:** missing a phishing site is usually more costly than a false
  alarm, so the URL detector should favour **high recall**. Blocks should come
  with a clear explanation and an easy "I trust this site" route, so false
  positives stay manageable.
- **Limitation:** static features cannot see a brand-new phishing page on a
  real hacked domain. This must be stated honestly in the report.

---

## b) Scam SMS and Smishing

"Smishing" means phishing by SMS. Scam texts do not need technical tricks.
They rely on **social engineering**: they push the reader to act quickly before
thinking.

### How the attack works in plain words

- **Impersonation:** the message pretends to be a bank, a delivery company, a
  tax office or the government.
- **Urgency linguistics:** words such as "immediately", "within 24 hours",
  "suspended", "final notice" or "last warning" create panic.
- **Reward or fear:** "You have won", "refund pending", "unpaid fine".
- **Call to action:** "click here", "reply YES", "call this number".
- **OTP harvesting:** the message asks for a one-time password (OTP), PIN or
  verification code. Real banks never ask for these by text, so this is a very
  strong clue.
- **Link hiding:** a short link (such as one from a URL shortener) hides the
  real destination.

### Static features we extract offline

| Feature | Example | Why it helps |
|---|---|---|
| Urgency word count | "urgent", "immediately", "24 hours" | Pressure is a core scam technique |
| OTP or PIN request | "share your OTP", "enter code" | Almost never legitimate |
| Money or prize words | "won", "refund", "fine", "prize" | Lure words |
| Contains a link | `bit.ly/...` | Links are the attack's delivery step |
| Link features | (reuse URL features above) | Connects SMS and URL detectors |
| Sender type | Alphanumeric sender vs. a normal mobile number | Impersonation uses fake sender names |
| Capital letters and exclamation marks | "ACT NOW!!!" | Shouting is common in scams |
| Message length and number of digits | | Scam texts often contain account or reference numbers |
| Character-level n-grams (TF-IDF) | word pairs such as "verify account" | Captures wording patterns automatically |

Note: the UCI SMS dataset in our shortlist contains message text only, without
sender information. So the sender feature cannot be trained on that dataset.

### False positive vs. false negative trade-off

- **False positive:** a genuine bank alert ("Your OTP is 123456, do not share
  it") contains "OTP" and "bank" and is flagged. This is a real risk, because
  the user may ignore a true security notice.
- **False negative:** a scam written in polite, ordinary language with no
  urgency words gets through.
- **Our stance:** the SMS detector should balance both. Because a real OTP
  notice is very common and useful, the explainer should present the alert as
  "possible scam, check before you act" rather than "this is a scam". The
  advisory should always show the reason, so the user can judge it.
- **Limitation:** the UCI dataset is English, and it is older. Scam text in
  other languages and newer scam styles are not covered.

---

## c) Network Intrusion and Flow Anomalies

Network attacks are visible in the **pattern** of traffic rather than in any
single packet. A flow is a summary of one connection (source, destination,
port, bytes, packets, flags, and so on). The detector looks at these summaries.

### How the attacks work in plain words

- **Port sweep (scan):** an attacker tries many ports or many hosts in a short
  time to find open doors. Many connections, few bytes each, many
  "rejected" replies.
- **DoS (denial-of-service) flood:** a huge number of connections or packets are
  sent to exhaust a service. Very high connection counts to the same service,
  often with many error flags.
- **Asymmetric traffic:** a normal download has many bytes coming back. An
  attack may send lots of bytes out and get almost nothing back (or the other
  way round), so the packet and byte counts are lopsided.
- **Repeated error rates:** many "SYN error" or "connection refused" states mean
  the connection attempts are not completing.

### Static features we extract from each flow

| Feature | Example | Why it helps |
|---|---|---|
| Duration | 0.0 seconds | Scans and floods are often very short |
| Source bytes and destination bytes | 0 bytes sent, 0 returned | Asymmetry and empty replies |
| Ratio of source to destination bytes | very large or very small | Lopsided traffic |
| Count of connections to same host (recent) | 300 in 2 seconds | Flood or scan behaviour |
| Count of connections to same service | many to port 22 | Brute-force or sweep |
| Error rate (SYN errors, REJ errors) | 0.95 | Failed handshakes |
| Same-service rate | 1.0 | Repeated attempts on one port |
| Number of distinct ports hit | 500 different ports | Port sweep signature |
| Logged-in flag and root-shell flag | 0 | Post-exploit clues |

**Dataset note:** NSL-KDD provides these features already computed. This
means our network detector can be trained and tested offline without a packet
capture tool. The limitation is that NSL-KDD is based on 1999 traffic, so its
attacks are older than what a phone sees today. The report must state this.

### False positive vs. false negative trade-off

- **False positive:** a backup job, a software update or a busy game server
  creates many connections and is flagged as a flood. The user sees a warning
  about normal activity.
- **False negative:** a slow, low-volume scan spread over hours stays below the
  count thresholds and is missed.
- **Our stance:** flooding and scanning are serious and should be caught early,
  so we accept some false alarms. To limit annoyance, the advisory should
  mention the **normal reasons** traffic can look like this, and the user can
  mark a trusted app or host as safe.
- **Limitation:** features computed over time windows need a little memory on
  the phone. This will be checked in the benchmark phase.

---

## Summary table

| Vector | Main signal | Main false positive risk | Main false negative risk | Our priority |
|---|---|---|---|---|
| Phishing URL | Disguised or random domain | Unusual but real domains blocked | Fresh domain on clean-looking name | High recall |
| Scam SMS | Urgency and OTP requests | Genuine OTP notices flagged | Polite scam with no pressure words | Balanced, explain reasons |
| Network flow | Lopsided or repeated traffic | Backups and updates flagged | Slow, low-volume scans | Catch floods and scans, explain context |
