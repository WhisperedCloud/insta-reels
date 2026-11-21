# Instagram Reels bot

Two faceless Instagram accounts, 2 Reels a day each, made and posted for free by GitHub Actions
(`.github/workflows/instagram_reels.yml`).

| Account | Format | Posts (UTC) |
|---|---|---|
| `quiz` | Guess the Place: footage of a famous place, 4 options, 5 s countdown, reveal + fact | 13:30 and 23:30 (7 PM India, 6:30 PM US East) |
| `stoic` | Animated quote Reels: English Stoic quotes at 01:30, Thanglish lines (Kural, proverbs, originals) at 16:00 | 01:30 and 16:00 (8:30 PM US East, 9:30 PM India) |

The workflow is triggered three times before each slot in `reels/slots.py` (80, 40 and 12 minutes ahead).
A run that starts within 15 minutes of the slot renders the Reel, waits and posts on time; a late run posts
straight away. GitHub starts scheduled jobs late and Instagram cannot schedule posts, and the repo is
private, so the job is kept short to stay inside the free 2,000 minutes a month.

Content sources: Pixabay footage (Pixabay Content License, free for commercial use, no credit needed), music
synthesised by `audio.py` (original), OFL fonts, quotes from ancient authors in a hand-checked list.

Every Reel is checked before posting (1080x1920, H.264/AAC, -14 LUFS). Used clips and quotes are logged in
`reels/used_*.txt` so nothing repeats.

## Setup

1. Copy `.env.example` to `.env` and fill it in (Gemini key, Pixabay key, Meta app ID + secret + user token,
   the two Instagram usernames).
2. Run `python3 reels/setup_secrets.py`. It saves everything as GitHub secrets, including a non-expiring
   Page token per Instagram account (`IG_TOKEN_QUIZ`, `IG_TOKEN_STOIC`).

Each Instagram account must be a Creator account linked to a Facebook Page. That connection is what allows
a track from Instagram's own music library to be attached; if that ever fails, the Reel is posted with its
built-in soundtrack instead. Set the repo variable `IG_MUSIC=off` to always use the built-in soundtrack.

Without an account's token, scheduled runs do nothing and manual runs only save the Reel under **Artifacts**.

## Test by hand

Actions → Instagram Reels → Run workflow → pick the account, keep **dry run** ticked to only render, untick to post.
