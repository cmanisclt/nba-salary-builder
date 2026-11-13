NBA DRAFT LAB — 2026–27 SALARY CAP SIMULATOR

YOUR PUBLIC STATIC WEBSITE (FREE NETLIFY HOSTING)
  Only index.html and players-data.js are needed online.
  1. Collect the salary database ONE TIME on your Mac:
       python3 build_static.py --refresh
     (If fetching fails, try: python3 app.py, open http://localhost:8765,
      click the Refresh button, then run: python3 build_static.py)
  2. Confirm the terminal says how many players it exported and that all
     30 teams were loaded. Player positions may be unclassified.
  3. Drag the nba_salary_builder folder to https://app.netlify.com/drop
     (Or make a separate folder containing ONLY index.html + players-data.js.)
  4. The published site loads bundled players-data.js without any server.
     Visitors never need Python or a HoopsHype connection.

IMPORTANT: The shipped players-data.js is a STARTER-POOL PLACEHOLDER ONLY.
Run the build command above to replace it with the real full-league data.
Do not claim the full database is loaded until you verify exported counts.
The site doesn't continuously update salaries; repeat refresh + upload to update.

ABOUT THE SIMULATOR
  3 guards, 4 forwards, 1 center, 2 flex. $250 million default ceiling.
  Roster and salary selections work in the browser. Browser local storage
  saves individual scenarios. The site exports CSV and scenario JSON.

SOURCE / DATA CHECKS
  HoopsHype salaries: https://www.hoopshype.com/salaries/players/
  HoopsHype salary data generally does not provide positional eligibility;
  position enrichment via ESPN may be incomplete. Review unclassified players.
  This is an educational planning simulator, not official NBA cap accounting.
  Check availability, contract details, and site usage conditions before use.
