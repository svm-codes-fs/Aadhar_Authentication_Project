# Presentation Guide

All numbers below are computed by the app from `data/aadhaar_auth_attempts.csv` (no filters applied).
Re-check them on the live pages before presenting: the app is the source of truth.

---

## 1. Ten-minute demo script

| Time | Page | What to show | What to say |
|---|---|---|---|
| 0:00–1:00 | **Overview** | Banner, then the KPI cards | "This is a simulation, not UIDAI data. We have 7,858 attempts by 2,000 invented beneficiaries over 6,000 visits. The FRR is 24.3%, so about one in four genuine attempts is rejected. The FAR is only 0.6%. The system is strict, and genuine people pay for that strictness. 159 genuine beneficiaries were denied at least once." |
| 1:00–2:30 | **Who Gets Excluded?** | Age-group charts, then occupation, then gender | "The orange bar is the worst group. People aged 75+ are denied on 21.7% of visits; people aged 18–30 on 1.3%. Manual occupations sit far above office workers. Gender is our **control**: the generator has no gender effect, and the bars are identical (3.3% vs 3.3%). This shows the method does not invent bias where none exists." |
| 2:30–3:45 | **Biometric Quality** | Quality-band chart, then the scatter | "Quality decides everything. Attempts with quality 20–40 fail 73.8% of the time; at 60–80 only 6.0%. In the scatter, genuine users below the dashed 0.60 line are rejected even though they are who they say they are. Iris has an FRR of 3.5% against 24.7% for fingerprints, but in this data iris is only available on high-quality devices." |
| 3:45–5:00 | **System Failures** | Reason chart, then the heatmap | "78.1% of failures are biometric and 21.9% come from the network or device. The heatmap is the key slide: Urban with a high-quality device has 0.5% denial; Remote with a low-quality device has 9.9%. Remote areas mostly receive low-quality devices." |
| 5:00–6:00 | **Repeated Failures** | Attempt chart and table | "'Just try again' does not work. Success drops from 79.8% on the first attempt to 55.6% on the third, because the cause (worn fingerprints, a bad device) is still there. 31 people were denied on two or more visits, which points to systematic exclusion rather than bad luck." |
| 6:00–7:30 | **Fairness Metrics** | Age table, sentence, odds-ratio chart | "The age gap fails the four-fifths rule badly: a ratio of 17.1 against a limit of 1.25, with p < 0.001. In the regression, age 75+ multiplies the odds of a failed first attempt by 7.5, construction work by 5.5 and a low-quality device by 4.3. Rural and Remote come out *below* 1 once device and network are included, so the area gap comes through infrastructure." |
| 7:30–9:00 | **Simulator** | Default profile (68, manual labourer, remote, low device, poor network, dusty), then **Compare** | "Watch three attempts fail or succeed live. Over 1,000 simulated visits this profile is denied about half the time. A young office worker with a good device is almost never denied. Same scheme, same rules, very different outcomes." |
| 9:00–10:00 | **Methodology** | Assumptions table, limitations, recommendations | "Every disparity comes from a documented line in this table, so the findings are *mechanisms*, not measurements of the real system. Our recommendations are fallback authentication (OTP, iris, manual override), better devices in remote areas, offline mode, and exemptions for the elderly and manual workers." |

**Tips:** set the browser zoom to 90% on a projector. Use a filter live once (e.g. *Area type = Remote* on Fairness
Metrics) to show that every chart is computed from the data.

---

## 2. Five key findings (computed numbers)

1. **Age is the strongest driver of exclusion.**
   Genuine people aged 75+ are denied on **21.7%** of visits, against **1.3%** for ages 18–30. That is **17.1×** the
   rate (chi-square p < 0.001). Their attempt-level FRR is **57.6%** against 16.5%. Logistic regression odds ratio for
   a failed first attempt: **7.52×** (75+ vs 18–30).

2. **Manual workers are excluded far more than office workers.**
   Denial rate: Farmer **5.8%**, Manual labourer **5.0%**, Construction worker **3.0%**, against Office/Skilled
   **0.1%** (p < 0.001). Odds ratios vs office workers: construction **5.46×**, manual labourer **4.32×**, farmer **4.11×**.

3. **Infrastructure, not geography itself, drives the rural/remote gap.**
   Remote areas are denied on **6.2%** of visits and urban areas on **1.7%** (**3.6×**, p < 0.001). Remote with a
   low-quality device: **9.9%**; urban with a high-quality device: **0.5%**. Once device and network are in the model,
   Rural (0.93×) and Remote (0.85×) have odds ratios below 1, while a low-quality device has **4.26×** and a poor
   network **1.75×**.

4. **Most failures are biometric, and capture quality decides the outcome.**
   **78.1%** of failed attempts are biometric (mismatch or poor capture) and **21.9%** are system failures (network or
   device). Genuine attempts with quality 20–40 fail **73.8%** of the time, against **6.0%** at 60–80. Iris FRR is
   **3.5%** against **24.7%** for fingerprints.

5. **The system is strict on security and costly for genuine users, and retries do not fix it.**
   FRR is **24.3%** while FAR is **0.6%**. Success falls from **79.8%** (attempt 1) to **63.1%** (attempt 2) to
   **55.6%** (attempt 3). **159** genuine beneficiaries were denied at least once and **31** on two or more visits.
   *Control check:* gender shows **3.32% vs 3.31%** denial (p ≈ 1.00), as expected, because the generator has no
   gender effect.

---

## 3. Likely viva questions with short answers

**1. Why synthetic data?**
Real Aadhaar authentication logs with biometric scores are not public, and using them would raise serious privacy
and legal issues. Synthetic data lets us study the *mechanisms* of exclusion safely, reproducibly (fixed seed) and
transparently (every assumption is visible).

**2. What is FRR vs FAR?**
FRR (False Rejection Rate) is the share of a *genuine* person's attempts that are rejected; it is computed on genuine
users only. FAR (False Acceptance Rate) is the share of an *impostor's* attempts that are accepted; it is computed on
impostors only. Raising the threshold lowers FAR but raises FRR. Here FRR is 24.3% and FAR is 0.6%.

**3. Is this real bias or assumed bias?**
It is assumed bias. Each disparity comes from a documented assumption, such as fingerprint quality falling after
age 55 or low-quality devices being more common in remote areas. The project does not prove the real system is
biased. It shows how plausible mechanisms *become* measurable exclusion, and that standard fairness metrics detect
them. The gender control group, with no effect built in, shows no gap, which supports the method.

**4. How would you fix it?**
Use fallback authentication (OTP, iris, or a logged manual override) so no one is denied on a biometric failure
alone. Replace low-quality devices in rural and remote areas first. Add an offline or deferred authentication mode
for network outages. Give elderly and manual workers exemptions or alternative proof. Publish FRR and denial rates by
group so they can be monitored.

**5. Why measure denial per visit and not per attempt?**
A person is excluded only when *all* attempts in a visit fail. Counting attempts would over-weight people who
retried. So visit-level metrics use one row per `session_id` (6,000 visits).

**6. Why exclude impostors from the denial rate in the bias analysis?**
Blocking an impostor is the system working correctly, not exclusion. Including them would mix security successes
with welfare failures. The Overview shows both: 5.2% of all visits and 3.3% of genuine visits.

**7. What is the four-fifths rule and why 1.25?**
It is a standard disparate-impact screen: a group's success rate should be at least 80% of the best group's. We
measure failure rates, so we flip it: a group fails if its denial rate is more than 1 ÷ 0.8 = 1.25 times the best
group's.

**8. What does the chi-square test tell you?**
It tests whether denial is independent of an attribute. A small p-value (< 0.05) means the gap between groups is very
unlikely to be chance. For age, p < 0.001. For gender, p ≈ 1.00, so there is no difference.

**9. Why use logistic regression, and what is an odds ratio?**
Group comparisons mix factors together. For example, remote areas also have worse devices. Logistic regression holds
the other factors constant. An odds ratio of 4.26 for a low-quality device means the odds of a failed first attempt
are 4.26 times those on a high-quality device, all else equal. We use first attempts of genuine users so each visit
counts once.

**10. What are the main limitations?**
The effect sizes are chosen by the modeller, not measured. The analysis can only recover mechanisms that were put in.
The generator was reconstructed from the dataset. Some groups are small (75+, iris users). Matching is simplified (no
multi-finger fusion). There is no time dimension. The regression ignores correlation between the same person's visits.
