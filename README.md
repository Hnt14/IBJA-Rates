# IBJA Gold & Silver (mobile web app)

Shows IBJA Gold 999 and Silver 999 rates, the day-over-day change, and the gold:silver ratio
(with a 30-day trend). Works as a home-screen app on your phone.

## One-time setup (about 5 minutes)

1. Create a new GitHub repository and upload everything in this folder (keep the `.github` folder).
2. Repo **Settings → Pages**: Source = "Deploy from a branch", Branch = `main`, folder = `/ (root)`.
3. Repo **Actions** tab → "Update IBJA rates" → **Run workflow** once, to fetch the first rates.
   (Settings → Actions → General → Workflow permissions must allow "Read and write".)
4. Open `https://<your-username>.github.io/<repo-name>/` on your phone.
   - Android Chrome: menu → Add to Home screen.
   - iPhone Safari: Share → Add to Home Screen.

After that it updates itself Mon–Fri around 12:15 PM (AM rates) and 6:15 PM IST (PM rates).
IBJA doesn't publish on weekends and holidays, so the app keeps showing the last published day.

## How the ratio is calculated

`ratio = (Gold 999 per gram) / (Silver 999 per gram) = Gold ₹/10g × 100 / Silver ₹/kg`

## Notes

- `scrape.py` reads the public table on ibjarates.com. If IBJA changes the page layout, the daily
  run will fail loudly (it won't write bad data) and the script's `parse()` needs a small tweak.
- IBJA asks commercial users to subscribe to its official API. This setup is for personal viewing.
- Test locally: `python scrape.py saved_page.html`
