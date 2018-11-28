import scrapy

class SubjectsSpider(scrapy.Spider):
	name = 'subjects'
	#start_urls = ['https://handbook.unimelb.edu.au/search?query=&year=2018&types%5B%5D=subject&level_type%5B%5D=undergraduate&study_periods%5B%5D=semester_1&study_periods%5B%5D=semester_2&study_periods%5B%5D=summer_term&study_periods%5B%5D=winter_term&study_periods%5B%5D=year_long&area_of_study=all&faculty=all&department=all']
	#start_urls = ['https://handbook.unimelb.edu.au/subjects/undergraduate']
	#start_urls = ['https://handbook.unimelb.edu.au/breadth-search?course=B-SCI']
	start_urls = ['https://handbook.unimelb.edu.au/subjects/']
	parse_count = 0
	total_count = 0

	def parse_requirements(self, response):
		data = response.meta['data']
		# handle prerequisites
		prereq = response.css("#prerequisites > *")[1:]
		
		# handle corequisites, non-allowed subjects, recommended background knowledge
		# Take each element of the body, except the title and 'core participation req.' stuff
		body = response.css('div.course__body > *')[2:-4]
		current = ""
		for element in body:
			text = element.css('::text').extract_first()
			if text == "Prerequisites": # has its own div .. for some reason!!
				data[current] = []
				for child in el.xpath('./*'): # go through each child in prereq div
					found = False
					for label in child.xpath('.//tr'):
						code = label.css('td::text').extract_first()
						if code is not None:
							data[current].append(code)
						found = True
					if found: #don't handle the table twice
						continue
					text2 = child.css('::text').extract_first()
					if text2 is not None:
						text2 = text2.strip()
					if text2 == current: # ignore name
						continue
					elif str(text2) != "None": # could be None or 'None'
						data[current].append(child.xpath('string(.)').extract_first().strip())
			elif text in ["Corequisites", "Non-allowed subjects", "Recommended background knowledge"]:
				current = text
				data[current] = []
			elif str(text) != "None": # TODO: clean this up (this finds the codes from the fancy table)
				found = False
				for label in el.xpath('.//tr'):
					code = label.css('td::text').extract_first()
					if code is not None:
						data[current].append(code)
					found = True
				if found: #don't handle the table twice
					continue
				data[current].append(el.xpath('string(.)').extract_first().strip()) #normal handle
		yield data
		
	def parse_subject(self, response):
		data = response.meta['data']
		data['weight'] = response.css('p.header--course-and-subject__details span ::text').extract()[1].split("Points: ")[1]
		# Parse infobox
		for line in response.css('div.course__overview-box tr'):
			field = line.css('th ::text').extract_first()
			value = line.css('td').xpath("string(.)").extract_first()
			if field == 'Availability':
				data[field] = [label.css("::text").extract_first() for label in line.xpath('.//td/div')]
			elif field == 'Fees' or field == "Year of offer"
				# skip
				pass
			else 
				data[field] = value
		# Parse overview paragraphs
		data['overview'] = response.css(".course__overview-wrapper p::text").extract_first();
		data['learning-outcomes'] = [x[:-1] for x in response.css("#learning-outcomes .ticked-list li ::text").extract()];
		data['skills'] = [x[:-1] for x in response.css("#generic-skills .ticked-list li ::text").extract()];
		# Get 'last updated' from page
		data['updated'] = response.css(".last-updated ::text").extract_first()[14:]
		yield scrapy.Request(
			response.urljoin(data["url"] + '/eligibility-and-requirements'),
			callback=self.parse_requirements,
			meta={'data': data}
		)
	# parses results page, list of subjects
	def parse(self, response):
		# follow links to subject pages
		for result in response.css('li.search-results__accordion-item'):
			total_count += 1
			# skip if subject is not offered.
			offered = result.css('span.search-results__accordion-detail ::text').extract()[1]
			if ("Not offered in" in offered):
				continue
			parse_count += 1
			data = {}
			data['no_total'] = total_count
			data['no'] = parse_count
			data['name'] = result.css('a.search-results__accordion-title ::text').extract_first()
			data['code'] = result.css('span.search-results__accordion-code ::text').extract_first()
			data['url'] = result.css('a.search-results__accordion-title ::attr(href)').extract_first()
			print("Parsing [p{}t{}] {} ({})".format(parse_count, total_count, data['title'], data['code']))

			yield scrapy.Request(
					response.urljoin(data['url']),
					callback=self.parse_subject,
					meta={'data': data}
				)

		# follow pagination links to next list of subjects
		next_page = response.css('span.next a ::attr(href)').extract_first()
		if next_page is not None:
			yield response.follow(next_page, self.parse)