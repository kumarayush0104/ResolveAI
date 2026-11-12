# ResolveAI — Hackathon Demo Video Script & Screen Action Guide

**Target Duration:** 2:30 – 3:00 Minutes  
**Audience:** Hackathon Judges & Technical Evaluators  
**Core Thesis:** ResolveAI turns 3-to-5-day payment disputes and double charges into a 30-second automated resolution using PayPal APIs, Gemini AI, and a deterministic policy safety gate.

---

## 🛠️ Pre-Recording Checklist
- [ ] Local server running at `http://127.0.0.1:8000` (or live at `https://resolveai-anss.onrender.com/`).
- [ ] Browser set to **100% zoom**, full screen, clean bookmarks bar.
- [ ] Initial role set to **Buyer** (via top AppBar switcher).
- [ ] Screen recorder set to 1080p / 60 FPS with clear microphone audio.

---

## ⏱️ Video Timeline Overview
```
[0:00 - 0:30] Act 1: The Problem & 3D Scroll Story
[0:30 - 1:05] Act 2: Buyer Checkout with Live PayPal Buttons
[1:05 - 1:45] Act 3: The Edge Case & Fault Injection Lab
[1:45 - 2:20] Act 4: AI Investigator & The Policy Gate (Core Hook)
[2:20 - 2:45] Act 5: Real-Time Resolution & Merchant Console
[2:45 - 3:00] Act 6: Conclusion & Value Proposition
```

---

## 🎬 Second-by-Second Video Script

### Act 1: The Problem & The 3D Scroll Story (0:00 – 0:30)

* **Visual on Screen:** Top of landing page. Smoothly scroll down through the 3D feature cards while the PayPal logo rotates.
* **Cursor / Action:** Scroll steadily to show the feature cards tilt with physics and reveal their values. Stop when the interactive phone frame comes into view.
* **Voiceover / What to Say:**
  > *"When an online payment times out or a mobile connection drops, buyers are left asking: 'Did my money go through?' and sellers ask: 'Should I ship the order?'*
  > 
  > *Today, buyers hit 'Retry' and get double-charged, or file banking disputes that take 3 to 5 business days to resolve.*
  > 
  > *This is ResolveAI — an autonomous payment recovery and dispute mitigation engine powered by PayPal APIs and AI. We replace blind retries with cryptographic, multi-source evidence reconciliation and deterministic policy safety gates. Let’s jump into the interactive demo."*

---

### Act 2: Buyer Catalog & PayPal Checkout (0:30 – 1:05)

* **Visual on Screen:** Inside the phone frame on desktop (showcasing the real 390×844 phone proportions and subtle 3D tilt tracking).
* **Cursor / Action:** Click **"Start a checkout"** (or tap **Checkout** in the bottom navigation bar). Click **"+ Add"** on a store item. Notice the cart total update dynamically in USD.
* **Voiceover / What to Say:**
  > *"We're on the buyer's screen. Sellers manage items and live prices through our catalog API. Let's add an item to our cart.*
  > 
  > *The server validates price consensus so buyers always pay the seller's verified amount.*
  > 
  > *Notice the official PayPal Smart Buttons SDK below. When buyers approve the payment, ResolveAI orchestrates the capture with real-time orders API reconciliation."*

---

### Act 3: The Edge Case & Fault Injection Lab (1:05 – 1:45)

* **Visual on Screen:** Case view showing a payment in an `UNKNOWN` or `PENDING` state.
* **Cursor / Action:** Click to open a case (e.g. Case #...). The wallet card displays status `UNKNOWN`. Point cursor to the top right **"🧪 Fault lab"** button and click it. A dark bottom sheet slides up. Click **"Scenario 1: Lost success response"** (or **"Drop success response"**). Close the sheet.
* **Voiceover / What to Say:**
  > *"Now imagine the nightmare scenario: the buyer's card was charged by PayPal, but a network drop lost the final HTTP response. The buyer's screen is stuck in UNKNOWN.*
  > 
  > *To prove our system handles real-world edge cases, let's open our built-in Fault Injection Lab.*
  > 
  > *We trigger a lost response fault. Real money doesn't move, but the policy engine treats it with real sandbox scrutiny. Watch the evidence timeline update instantly over Server-Sent Events."*

---

### Act 4: The Secret Sauce — AI Investigator + Policy Gate (1:45 – 2:20)

* **Visual on Screen:** Case view action buttons showing a locked "Retry payment" button.
* **Cursor / Action:**
  1. **Click the locked "Retry payment" button.** Watch the card perform the **Shield-Shake animation** and pop the Policy Sheet showing `R03_UNKNOWN_FAILS_CLOSED`.
  2. Close the sheet.
  3. Click the glowing button: **"Run AI check"**. Watch the staggered tool lookup chips appear with animated shimmers, followed by the plain-language breakdown.
* **Voiceover / What to Say:**
  > *"The buyer naturally wants to tap 'Retry payment'. But watch what happens when I click it:*
  > 
  > *The Policy Gate blocks the action with a shield shake! Rule R03: 'Unknown outcome fails closed — a retry is strictly forbidden until PayPal confirms a definitive failure.' Double-charging is mathematically impossible.*
  > 
  > *Now let's resolve it. I'll click 'Run AI check'.*
  > 
  > *In seconds, Gemini queries PayPal Orders and Transaction Search APIs. It proves the capture was actually completed, explains what happened in plain English for both parties, and links verified evidence on the timeline."*

---

### Act 5: Real-Time Resolution & Merchant Console (2:20 – 2:45)

* **Visual on Screen:** Payment transitions to `COMPLETED`. Confetti explodes 🎉 and the green expanding ring pulses around the status badge.
* **Cursor / Action:** Point to the **StateMachineViz** path lighting up. Then switch role to **Seller / Admin** in the top AppBar and navigate to **Console**. Show the KPI cards and animated volume chart.
* **Voiceover / What to Say:**
  > *"Instantly, the state machine transitions to COMPLETED. The buyer gets their verified receipt, the seller is notified to fulfill the order, and the retry button is permanently locked by Rule R01.*
  > 
  > *Switching over to the Merchant Console: sellers and support teams get full visibility — real-time dispute metrics, duplicate charges blocked by rule ID, item pricing management, and live webhook monitoring."*

---

### Act 6: Conclusion (2:45 – 3:00)

* **Visual on Screen:** Return to Landing view or show the framed phone mockup edge-to-edge.
* **Cursor / Action:** Move cursor gently to show the subtle 3D tilt perspective.
* **Voiceover / What to Say:**
  > *"By combining PayPal's authoritative transaction APIs with an AI investigator and a deterministic policy safety guard, ResolveAI turns 3-day disputes into 30-second automated resolutions.*
  > 
  > *Thank you!"*

---

## 🏆 Key Talking Points to Impress Judges
1. **Safety First Architecture:** Make sure to stress that **AI never directly executes money movements**. Gemini investigates and drafts plain-English explanations, but the **Deterministic Policy Engine (Rules R01–R07)** enforces the financial invariant rules.
2. **Authoritative Single Source of Truth:** We never trust client state; we verify against PayPal's Orders and Transaction Search APIs.
3. **No Double-Charge Guarantee:** Rule R01 blocks retries after completion; Rule R03 fails closed on unknown states.
