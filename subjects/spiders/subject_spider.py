import scrapy
disable_honours = True

class SubjectsSpider(scrapy.Spider):
	name = 'subjects'
	#start_urls = ['https://handbook.unimelb.edu.au/search?query=&year=2018&types%5B%5D=subject&level_type%5B%5D=undergraduate&study_periods%5B%5D=semester_1&study_periods%5B%5D=semester_2&study_periods%5B%5D=summer_term&study_periods%5B%5D=winter_term&study_periods%5B%5D=year_long&area_of_study=all&faculty=all&department=all']
	#start_urls = ['https://handbook.unimelb.edu.au/subjects/undergraduate']
	#start_urls = ['https://handbook.unimelb.edu.au/breadth-search?course=B-SCI']
	start_urls = ['https://handbook.unimelb.edu.au/subjects/']
	count = 0

	def parse_requirements(self, response):
		data = response.meta['data']
		main = response.css('div.course__body').xpath('./*')
		current = ""
		for el in main:
			text = el.css('::text').extract_first()
			if text is not None:
				text = text.strip()
			if text == 'Eligibility and requirements': # begin info
				continue
			elif text == "Core participation requirements": # end of info
				break
			elif text == "Prerequisites": # has its own div .. for some reason!!
				current = "Prerequisites"
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
		data['credit'] = response.css('p.header--course-and-subject__details span ::text').extract()[1].split("Points: ")[1]
		print(data['credit'])

		for line in response.css('div.course__overview-box tr'):
			name = line.css('th ::text').extract_first()
			entry = line.css('td').xpath("string(.)").extract_first()
			# we don't care about Honours subjects at the moment.
			if disable_honours and name == "Subject level" and entry == "Honours":
				yield '' # this will just make an error, that's ok, it removes it from the output
				return
			if name == 'Availability':
				data[name] = []
				for label in line.xpath('.//td/div'):
					data[name].append(label.css("::text").extract_first())
			elif name in ["Campus", "Subject level"]:
				data[name] = entry
		print("Parsing [{}] {}".format(data['code'], data['title']))
		yield scrapy.Request(
			response.urljoin(data["href"] + '/eligibility-and-requirements'),
			callback=self.parse_requirements,
			meta={'data': data}
		)

	def parse(self, response):
		# follow links to subject pages
		for result in response.css('li.search-results__accordion-item'):
			data = {}
			offered = result.css('span.search-results__accordion-detail ::text').extract()[1]
			if ("Not offered" in offered): #skip!
				continue
			data['title'] = result.css('a.search-results__accordion-title ::text').extract_first()
			data['code'] = result.css('span.search-results__accordion-code ::text').extract_first()
			data['href'] = result.css('a.search-results__accordion-title ::attr(href)').extract_first()

			yield scrapy.Request(
					response.urljoin(data['href']),
					callback=self.parse_subject,
					meta={'data': data}
				)

	# follow pagnation links
		next_page = response.css('span.next a ::attr(href)').extract_first()
		if next_page is not None:
			yield response.follow(next_page, self.parse)