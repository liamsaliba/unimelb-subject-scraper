import scrapy	
import datetime

class SubjectsArchiveSpider(scrapy.Spider):
	name = 'archive-subjects'
	start_urls = [
				  'http://archive.handbook.unimelb.edu.au/', # archive
				  'https://handbook.unimelb.edu.au/2017/subjects', # modern
				  'https://handbook.unimelb.edu.au/2018/subjects', # modern
		     	  'https://handbook.unimelb.edu.au/2019/subjects', # modeern
				 ]

	def parse_page(self, response):
		"""
		Parses list of subjects in modern handbook.
		"""
		year = response.meta['year']
		count = response.meta['count']
		for result in response.css('li.search-results__accordion-item'):
			subject = {}
			subject['Name'] = result.css('a.search-results__accordion-title ::text').extract_first()
			subject['Code'] = result.css('span.search-results__accordion-code ::text').extract_first()
			subject['Year'] = year
			count += 1
			yield subject
		
		# Follow pagination links to next list of subjects
		next_page = response.css('span.next a ::attr(href)').extract_first()
		if next_page is not None:
			print("Page exhausted. Navigate to", next_page, "count:", count)
			yield response.follow(next_page, self.parse_page, meta={'year': year, 'count': count})
		else:
			print("Finished parsing {} ({} subjects parsed)".format(year, count))

	def parse_subject_list(self, response):
		"""
		Parse archived handbook subject page
		"""
		year = int(response.css("h1::text").extract_first()[:4])
		count = 0
		for line in response.css("ul li"):
			subject = {}
			subject['Code'] = line.css(".code ::text").extract_first()
			subject['Name'] = line.css("a ::text").extract_first()
			subject['Year'] = year
			count += 1
			yield subject
		print("Finished parsing {} ({} subjects parsed)".format(year, count))

	# Parse results page, list of subjects
	def parse(self, response):
		"""
		Parse start url -- either modern or archived handbook pages.
		"""
		url = response.request.url.split('/')

		# Parsing modern handbook pages.
		if url[2][:8] == 'handbook':
			year = int(url[-2])
			yield response.follow(response.request.url, self.parse_page, meta={'year': year, 'count': 0})
		# Parsing archived handbook pages.
		else:
			# Multiple years on one page -- parse each years' pages.
			for link in response.css("ul li a"):
				href = link.css("::attr(href)").extract_first()
				if "subject" not in href:
					continue
				# Parse the subjects of a year.
				name = link.css("::text").extract_first()
				year = int(name[:4])
				if year <= 2007:
					print("Skipping", name)
					continue
				print("Parsing", name, "at", href)
				yield response.follow(link, self.parse_subject_list)