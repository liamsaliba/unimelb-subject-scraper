# unimelb-subject-scraper
Scrapes subjects off of the University of Melbourne Handbook
Also scrapes the timetable for each subject from sws.unimelb.edu.au.

Run the crawler and output to a json file.  
```
scrapy crawl subjects -o subjects.json
```
File will be approximately 50MB.  At a later date, will make a converter to some database.

Core code is found in /subjects/spiders/subject_spider.py.
Made to learn how to scrape websites using scrapy.  May be used to make an app in the future.
