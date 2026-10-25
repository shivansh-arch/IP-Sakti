- NIIMH chapters mix short root verses with long prose commentary
- Commentary blocks close with the same ||N|| marker as their verse — alignment is reliable, no separate matching needed
- Verse count per chapter varies widely; don't assume ~30 verses/chapter, check each one
- NIIMH full scrape complete: 126 chapters, 3949 sub-section files, 0 failures
- Saved to data/raw/niimh/{sthana}_{adhyaya}_{suc}.html
- Chikitsasthana (sthana=6) has nested chapter numbering (e.g. "1/1", "1/2")
  for Rasayana and Vajikarana sub-chapters - adhyaya_val doesn't map 1:1 to
  display chapter number, use adhyaya_val as the real key