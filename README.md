# poker-bot 🃏

A No-Limit Texas Hold'em bot built for the [Fullhouse Hackathon 2026](https://fullhousehackathon.com) — London, 1–5 June 2026.

---

## Strategy Overview

The bot classifies starting hands into three tiers and adapts its aggression based on the **Stack-to-Pot Ratio (SPR)** at each street.

### Hand Classification

| Tier | Examples | Preflop Action |
|------|----------|----------------|
| **Strong** | AA, KK, QQ, JJ, TT, 99, 88, AK, AQ, AJ, AT, KQ, KJ, QJ | Raise 3x BB (or all-in if short stacked) |
| **Medium** | Suited connectors (JTs, 98s…), other playable hands | Call if price is right |
| **Weak** | Low pairs (22–55), unconnected low cards (72o, 83o…) | Fold (check if in the blind) |

### SPR-Based Sizing

SPR = `your_stack / pot`

| SPR | Stack Depth | Strong Hand Action |
|-----|-------------|-------------------|
| < 3 | Short stack | **All-in** on any street |
| 3–6 | Medium stack | All-in from the flop onwards |
| > 6 | Deep stack | Bet 50% pot (lead) / 75% pot (re-raise) |

### Street-by-Street Logic

- **Preflop** — raise strong hands, call medium hands at a reasonable price, fold weak hands
- **Flop** — strong hands bet for value and protection; no free cards given
- **Turn** — commit with strong hands if SPR < 6; otherwise size up to build the pot
- **River** — shove if short-stacked; value-bet 50–75% pot when deep

---

## Running the Bot

### Prerequisites

```bash
# Requires Python 3.10 (eval7 is not compatible with 3.11+)
pip install "Cython<3"
pip install --no-build-isolation eval7==0.1.7
pip install flask numpy scipy treys scikit-learn
```

### Single match against a reference bot

```bash
git clone https://github.com/uzlez/fullhouse-engine
cd fullhouse-engine

python3 sandbox/match.py /path/to/bot.py bots/shark/bot.py --hands 400 --verbose
```

### Available reference bots

| Bot | Style |
|-----|-------|
| `bots/shark/bot.py` | Tight-aggressive, position-aware |
| `bots/aggressor/bot.py` | Raises every hand |
| `bots/mathematician/bot.py` | Calls only at 3:1 pot odds |
| `bots/ref_bot_2/bot.py` | Pot-odds caller |
| `bots/template/bot.py` | Basic pocket-pair bot |

### Validate before submitting

```bash
make -C fullhouse-engine validate BOT=/path/to/bot.py
```

---

## File Structure

```
bot.py      # The bot — only file needed for submission
README.md
LICENSE
```

---

## Competition

**Fullhouse Hackathon** · 1–5 June 2026 · London  
Prize pool: £4,000+ · Sponsored by Quadrature Capital  
Submission deadline: **31 May 2026, 23:59 UTC**

---

## License

MIT
