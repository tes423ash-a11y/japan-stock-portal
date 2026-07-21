# State

Technical SEPA/VCP v4 is implemented as a full-market JP/US scan with the best 1000 rows published to the mobile dashboard.

- all TSE domestic common stocks and eligible U.S. major-market common stocks screened first
- 500 JP and 500 US rows in the published dashboard report
- JPX-backed Japanese company names and sectors
- Cross-sectional RS, trend template, VCP, volume, risk and liquidity scoring
- Sector relative strength and post-detection daily-close tracking
- Mobile dashboard filters and regression tests
- reusable per-market base-metric feeds under `reports/shared/` for other stock-selection views

Fundamentals, earnings dates and news remain intentionally outside the technical score.
