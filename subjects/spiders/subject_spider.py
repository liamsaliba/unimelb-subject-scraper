import scrapy	
import datetime

def remove_blanks(l):
	return [x for x in l if x != ""]

def parse_element(element):
	""" Function can return None, be careful!"""
	# traverse list (if element is one)
	ul = element.xpath(".//li")
	if len(ul) != 0:
		return {"type" : "list", "val" : ul.css("::text").extract()}
	# treat as just text	
	string = element.xpath("string(.)").extract_first().strip()
	# TODO: possibly check if it is a "\n" and turn it into a 'None' ?
	if string == "None" or string == "Nil" or string == "":
		return None
	if string == "\n  ":
		print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
		return None
	return {"type" : "text", "val" : string}

def parse_element_with_subject_table(element):
	# traverse table (if element is one)
	table = element.xpath(".//tr")
	if len(table) != 0:
		current = {"type" : "subj", "val" : []}
		for row in table[1:]:
			# take only the subject code
			current["val"].append(row.css("td::text").extract_first())
		return current
	return parse_element(element)

class SubjectsSpider(scrapy.Spider):
	name = 'subjects'
	start_urls = ['https://handbook.unimelb.edu.au/subjects/']
	parse_count = 0
	parsed_count = 0
	total_count = 0
	period_store = []
	
	def log(self, data, step, lv='*'):
		print("{} [{:4d}/{:4d}/{:4d}] ({}) Parse {:5} ({:4d}) {}  {}".format(datetime.datetime.now().isoformat(' '), self.parsed_count, self.parse_count, self.total_count, lv, step, data['Parse No.'], data['Code'], data['Name']))


	def parse_timetable(self, response):
		data = response.meta['data']
		timetable = {}
		tables = response.css("div table")
		for period in [x.strip("\n\t ").split("\xa0")[0][9:] for x in response.css("div h3")]:



		data['Timetable'] = timetable

		# Logging
		self.parsed_count += 1
		self.log(data, "done", '-')
		data["Parsed No."] = self.parsed_count
		yield data

	def parse_further_info(self, response):
		data = response.meta['data']
		further_information = {}
		further_information['Texts'] = response.css(".texts .accordion__hidden > *:nth-child(n+2) ::text").extract()
		further_information['Notes'] = response.css(".notes .accordion__hidden > * ::text").extract()
		# Related
		related = []
		for row in response.css(".related tbody tr"):
			item = {}
			temp = row.css("td ::text").extract()
			item["type"] = temp[0]
			item["name"] = temp[1]
			item["href"] = row.css("a ::attr(href)").extract_first()
			related.append(item)
		further_information['Related'] = related
		# Breadth
		further_information['Breadth'] = response.css(".breadth li a::text").extract()

		further_information['Community Access Program'] = len(response.css(".community-access")) > 0
		further_information['Exchange/Study Abroad'] = len(response.css(".mobility-students")) > 0

		data["Further Information"] = further_information

		self.log(data, "furth")

		yield scrapy.Request(
			response.urljoin("https://sws.unimelb.edu.au/2019/Reports/List.aspx?objects=" + data['Code'] + "&weeks=1-52&days=1-7&periods=1-56&template=module_by_group_list"),
			callback=self.parse_timetable,
			meta={'data': data}
		)

	def parse_date_info(self, response):
		data = response.meta['data']
		# Dates
		dates = []

		accordion = response.css(".accordion > li")
		for semester in accordion:
			period = {"Name" : semester.css(".accordion__title::text").extract()}
			for row in semester.css("tr"):
				# populate rows
				a = row.css("::text").extract()
				period[a[0]] = a[1] if len(a) > 1 else None
			period["Contact Details"] = [x.strip(" \n\r") for x in semester.css(".course__body__inner__contact_details > *").xpath("string(.)").extract()]
			dates.append(period)
		data["Dates"] = dates
		# Additional Delivery Details
		a = response.css("course__body > *")
		temp = []
		if len(a) > 5:
			for line in a[5:-1]:
				temp.append(line.xpath("string(.)"))
		data["Additional Delivery Details"] = temp
		
		self.log(data, "date")

		yield scrapy.Request(
			response.urljoin(data["url"] + '/further-information'),
			callback=self.parse_further_info,
			meta={'data': data}
		)

	def parse_assessment(self, response):
		data = response.meta['data']
		assessment = {}
		table = response.css(".assessment-table tr")
		assessment["Assessments"] = []
		if len(table) != 0:
			for row in table[1:]:
				current = {}
				a = row.css("td")[0].css("li::text").extract()
				current["Name"] = a[0]
				current["Info"] = a[1:]
				a = row.css("td::text").extract()
				current["Timing"] = a[0]
				current["Weight"] = a[1]
		description_body = response.css(".assessment-description > *")
		if len(description_body) != 0:
			description = []
			for element in description_body[1:]:
				string = parse_element(element)
				if string is not None:
					description.append(string)
			assessment["Description"] = description
		data["Assessment"] = assessment
		
		self.log(data, "assmt")

		yield scrapy.Request(
			response.urljoin(data["url"] + '/dates-times'),
			callback=self.parse_date_info,
			meta={'data': data}
		)

	def parse_requirements(self, response):
		data = response.meta['data']
		requirements = {}
		# handle prerequisites
		prereq_body = response.css("#prerequisites > *")[1:]
		prereq = []
		for element in prereq_body:
			parsed = parse_element_with_subject_table(element)
			if parsed is not None:
				prereq.append(parsed)
		requirements['Prerequisites'] = prereq
		# handle corequisites, non-allowed subjects, recommended background knowledge
		# Take each element of the body, except the title and 'core participation req.' stuff
		body = response.css('div.course__body > *')[2:-4]
		# Include recommended background knowledge - not every page has it.
		requirements['Recommended background knowledge'] = []
		section_name = ""
		for element in body:
			extracted = element.extract()
			# line is a heading line -- next heading
			if extracted[:3] == "<h3":
				section_name = element.css("::text").extract_first()
				requirements[section_name] = []
				continue
			parsed = parse_element_with_subject_table(element)
			# Don't append if None, leave it blank
			if parsed is not None:
				requirements[section_name].append(parsed)
		data["Requirements"] = requirements

		self.log(data, "reqir")
		yield scrapy.Request(
			response.urljoin(data["url"] + '/assessment'),
			callback=self.parse_assessment,
			meta={'data': data}
		)
		
	def parse_subject(self, response):
		data = response.meta['data']
		
		head = response.css('p.header--course-and-subject__details ::text').extract()
		data['Level'] = head[0]
		if len(head) == 3:
			data['Weight'] = head[1][8:] 
			data['Location'] = head[2]
		else:
			data['Location'] = head[1]

		# Parse infobox
		for line in response.css('div.course__overview-box tr'):
			field = line.css('th ::text').extract_first()
			value = line.css('td').xpath("string(.)").extract_first()
			if field == 'Availability':
				data[field] = [label.css("::text").extract_first() for label in line.xpath('.//td/div')]
			# don't parse these
			elif field == 'Year of offer'
				data[field] = value
		# Parse overview paragraphs
		data['Info'] = {}
		data['Info']['Overview'] = remove_blanks([x.strip(' \n\r') for x in response.css(".course__overview-wrapper > p").xpath("string(.)").extract()])
		data['Info']['Learning Outcomes'] = remove_blanks([x.strip(' \n\r,.;') for x in response.css("#learning-outcomes .ticked-list li ::text").extract()])
		data['Info']['Skills'] = remove_blanks([x.strip(' \n\r,.;') for x in response.css("#generic-skills .ticked-list li ::text").extract()])
		# Get 'last updated' from page
		data['Updated'] = response.css(".last-updated ::text").extract_first()[14:]

		self.log(data, "subjt")

		yield scrapy.Request(
			response.urljoin(data["url"] + '/eligibility-and-requirements'),
			callback=self.parse_requirements,
			meta={'data': data}
		)
	# parses results page, list of subjects
	def parse(self, response):
		# follow links to subject pages
		for result in response.css('li.search-results__accordion-item'):
			self.total_count += 1
			# skip if subject is not offered.
			offered = result.css('span.search-results__accordion-detail ::text').extract()[1]
			if ("Not offered in" in offered):
				continue
			self.parse_count += 1
			data = {}
			data['Item No.'] = self.total_count
			data['Parse No.'] = self.parse_count
			data['Name'] = result.css('a.search-results__accordion-title ::text').extract_first()
			data['Code'] = result.css('span.search-results__accordion-code ::text').extract_first()
			data['url'] = result.css('a.search-results__accordion-title ::attr(href)').extract_first()
			self.log(data, "start", '+')

			yield scrapy.Request(
					response.urljoin(data['url']),
					callback=self.parse_subject,
					meta={'data': data}
				)

		# follow pagination links to next list of subjects
		next_page = response.css('span.next a ::attr(href)').extract_first()
		if next_page[-1] == '4':
			return
		if next_page is not None:
			print("Page exhausted. Navigate to", next_page)
			yield response.follow(next_page, self.parse)