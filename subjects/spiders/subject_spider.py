import scrapy	
import datetime
# Column names within timetable (sws)
TT_COL_NAMES = ['Class Code', 'Description', 'Day', 'Start', 'Finish', 'Duration', 'Weeks', 'Location', 'Class Dates', 'Start Date']
CURRENT_YEAR = 2019
NONE_STR = ["None", "Nil", "", "N/A", '\n']

def remove_blanks(l):
	"""
	Removes blank string entries within a list.
	"""
	return [x for x in l if x != ""]

def parse_element(element):
	""" Function can return None, be careful!"""
	# traverse list (if element is one)
	ul = element.xpath(".//li")

	if len(ul) != 0:
		vals = [x.strip() for x in ul.css("::text").extract()]
		return {"type" : "list", "val" : NONE_STR}

	# treat as just text	
	string = element.xpath("string(.)").extract_first().strip()

	if string in NONE_STR:
		return None

	return {"type" : "text", "val" : string}

def parse_element_with_subject_table(element):
	# traverse table (if element is one)
	table = element.xpath(".//tr")

	if len(table) == 0:
		return parse_element(element)

	current = {"type" : "table", "val" : []}

	for row in table[1:]:
		# take only the subject code
		x = row.css("td").xpath("string(.)").extract()

		if len(x) == 0:
			continue

		current["val"].append([x[0].strip(), None if len(x) == 1 else x[1].strip()])

	return current
	

class SubjectsSpider(scrapy.Spider):
	name = 'subjects'
	start_urls = ['https://handbook.unimelb.edu.au/subjects/']
	parse_count = 0
	parsed_count = 0
	total_count = 0
	
	def log(self, data, step, lv='*'):
		print("{} [{:4d}/{:4d}/{:4d}] ({}) Parse {:5} ({:4d}) {}  {}".format(datetime.datetime.now().isoformat(' '), self.parsed_count, self.parse_count, self.total_count, lv, step, data['Parse No.'], data['Code'], data['Name']))

	def parse_timetable(self, response):
		data = response.meta['data']
		timetable = {}
		# gives COMP20007/U/1/SM1
		period_names = [x.strip("\n\t ").split("\xa0")[0][9:] for x in response.css("div h3 ::text").extract()]
		tables = response.css("table.cyon_table")
		for i, table in enumerate(tables):
			parts = period_names[i].split("/")
			# Wondering if it's possible to not have those values ...
			# parts[1] shows the campus (U = Parkville)
			if parts[2] != "1":
				print("DEBUG: Period end not 1  !!", period_names[i])

			sem = parts[3]
			
			events = []
			for row in table.css("tbody tr"):
				# values within row (have to do this in a bizarre order for it to work!)
				values = [x.css("::text").extract() for x in row.css("td")]
				# convert to dictionary; preserve blanks and preserve lists
				event = dict([col, values[i]] for i, col in enumerate(TT_COL_NAMES))
				event["Subject Name"] = data["Name"]
				events.append(event)
			timetable[sem] = events

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
			response.urljoin("https://sws.unimelb.edu.au/" + str(CURRENT_YEAR) + "/Reports/List.aspx?objects=" + data['Code'] + "&weeks=1-52&days=1-7&periods=1-56&template=module_by_group_list"),
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

	def parse_overview(self, response):
		data = response.meta['data']
		
		head = response.css('p.header--course-and-subject__details ::text').extract()
		infobox = response.css('div.course__overview-box tr')

		# Get 'last updated' from page
		data['Updated'] = response.css(".last-updated ::text").extract_first()[14:]
		
		# Will be "Undergraduate Level #", 
		data['Level'] = head[0]

		# Most Subjects ...
		if len(head) == 3:
			data['Weight'] = head[1][8:] 
			data['Location'] = head[2]
		# Doctorate time-based research
		else:
			data['Location'] = head[1]
			# TODO: Process further:
				# Maximum EFTSL to complete
				# "Equivalent Full Time Study Load"
			yield data
			return

		# Parse infobox
		for line in infobox:
			field = line.css('th ::text').extract_first()
			value = line.css('td').xpath("string(.)").extract_first()
			if field == 'Availability':
				data[field] = [label.css("::text").extract_first() for label in line.xpath('.//td/div')]
			# Don't need  the others!
			elif field == 'Year of offer':
				data[field] = value
		# Parse overview paragraphs
		data['Info'] = {}
		data['Info']['Overview'] = remove_blanks([x.strip(' \n\r') for x in response.css(".course__overview-wrapper > p").xpath("string(.)").extract()])
		data['Info']['Learning Outcomes'] = remove_blanks([x.strip(' \n\r,.;') for x in response.css("#learning-outcomes .ticked-list li ::text").extract()])
		data['Info']['Skills'] = remove_blanks([x.strip(' \n\r,.;') for x in response.css("#generic-skills .ticked-list li ::text").extract()])

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
			
			# Don't parse the subject if the subject is not offered this year.
			# TODO: Parse the subject anyway, for information - ie, why not offered? (10/07/2019)
			offered = result.css('span.search-results__accordion-detail ::text').extract()[1]
			if ("Not offered in" in offered):
				continue
			self.parse_count += 1

			# Basic information parsed from results page.
			data = {}
			data['Item No.'] = self.total_count
			data['Parse No.'] = self.parse_count
			data['Name'] = result.css('a.search-results__accordion-title ::text').extract_first()
			data['Code'] = result.css('span.search-results__accordion-code ::text').extract_first()
			data['url'] = result.css('a.search-results__accordion-title ::attr(href)').extract_first()

			self.log(data, "start", '+')
			
			# Go on to parse subject overview
			yield scrapy.Request(
					response.urljoin(data['url']),
					callback=self.parse_overview,
					meta={'data': data}
				)

		# Follow pagination links to next list of subjects
		next_page = response.css('span.next a ::attr(href)').extract_first()

		# If debugging, end after scraping 3 pages.
		if DEBUG_SHORT_SCRAPE and next_page[-1] == '4':
			return

		# Go to next page, if there are any pages left to process.
		if next_page is not None:
			print("Page exhausted. Navigate to", next_page)
			yield response.follow(next_page, self.parse)
