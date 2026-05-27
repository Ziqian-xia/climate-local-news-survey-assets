# Climate Local News Survey Assets

This repository contains the Qualtrics QSF and hosted assets for the climate attribution in local news survey.

## Files

- `qsf/Climate_Local_News_-_Initial_may14_revised_congress_lookup_article_images.qsf`: upload this file to Qualtrics.
- `assets/treatment_article_images/`: single-column PNG versions of the 15 treatment articles.
- `data/representative_lookup_from_us_zipcodes_congress.csv`: ZIP/ZCTA to congressional representative lookup used by the letter question.
- `scripts/`: local scripts used to generate the images, representative lookup, and revised QSF.

## Qualtrics Embedded Data URLs

The QSF already sets these embedded data values for this repo:

```text
articleImageBaseUrl = https://raw.githubusercontent.com/Ziqian-xia/climate-local-news-survey-assets/main/assets/treatment_article_images/
representativeLookupCsvUrl = https://raw.githubusercontent.com/Ziqian-xia/climate-local-news-survey-assets/main/data/representative_lookup_from_us_zipcodes_congress.csv
```

If the repository name, owner, or default branch changes, update those two embedded data fields in Survey Flow before fielding.

## Data Sources

- ZIP/ZCTA to congressional district: https://github.com/OpenSourceActivismTech/us-zipcodes-congress
- District to current member: https://github.com/unitedstates/congress-legislators

Note: ZIP/ZCTA matching is approximate. Some ZIPs span multiple congressional districts, so the survey displays a representative selection question when multiple matches are found.
