# -*- coding: utf-8 -*-

from scrapy.spiders import CrawlSpider
from scrapy import Request, FormRequest
from scrapy.utils.request import request_fingerprint
from ResearchGateSpider.items import RGPersonItem, RGArticleItem
from ResearchGateSpider.datafilter import DataFilter
from ResearchGateSpider.func import parse_text_by_multi_content
from scrapy.exceptions import CloseSpider
import pymongo
import pandas as pd
import hashlib
import time
import redis

class RGSpider1(CrawlSpider):
    name = 'RGSpider1'
    domain = 'https://www.researchgate.net'
    # Check the finished url from MongoDB and create the final start_urls
    # client = pymongo.MongoClient(
    #     "127.0.0.1",
    #     27017
    # )

    # db = client["Research_Gate"]
    # collection = db['original_url']
    # origin_urls = collection.find()

    # link_list = []
    # for link in origin_urls:
    #     link_list.append(link['url'])
    # client.close()

    conn = redis.Redis('127.0.0.1', 6379)
    all_urls = conn.hgetall('rg_chinese')
    link_list = all_urls.values()

    print("There are %i urls to be crawl" % len(link_list))
    time.sleep(5)
    start_urls = link_list
    print("#####################################")
    print len(start_urls)
    # start_urls = ['https://www.researchgate.net/profile/Hui_Zhang106',]

    def parse(self, response):
        return self.parse_candidate_overview(response)

    def parse_candidate_overview(self, response):
        if response.status == 429:
            # lostitem_str = 'lost overview: ' + response.url
            # self.lostitem_file.write(lostitem_str)
            # self.lostitem_file.close()
            client = pymongo.MongoClient(
                "118.190.45.60",
                27017
            )
            db = client["RG_Chinese"]
            auth_result = db.authenticate(name='eol_spider', password='m~b4^Uurp)g', mechanism='SCRAM-SHA-1')
            collection = db['lost_url']
            collection.insert_one({'lost_usl':response.url, 'type':'overview'})
            client.close()
            raise CloseSpider(reason='被封了，准备切换ip')
        print '-----------start to process: ' + response.url
        headers = response.request.headers
        headers["referer"] = response.url

        item = RGPersonItem()

        featured_researches = response.xpath('//div[contains(@class, "profile-highlights-publications")]').extract()
        address = DataFilter.simple_format(response.xpath('//div[contains(@class, "institution-location")]/text()').extract())
        add_list = address.split(',')
        add_len = len(add_list)
        if add_len == 3:
            city = add_list[0].strip()
            province = add_list[1].strip()
            country = add_list[2].strip()
        elif add_len == 2:
            city = add_list[0].strip()
            province = ''
            country = add_list[1].strip()
        elif add_len == 1:
            city = add_list[0].strip()
            province = ''
            country = ''
        else:
            city = address
            province = ''
            country = ''
        # person_key = request_fingerprint(response.request)
        person_key = hashlib.sha256(response.url).hexdigest()
        item['person_key'] = person_key
        item['fullname'] = DataFilter.simple_format(response.xpath('//a[@class = "ga-profile-header-name"]/text()').extract())
        item['target_sciences'] = DataFilter.simple_format(response.xpath('//*[@id="target-sciences"]/text()').extract())
        item['title'] = DataFilter.simple_format(response.xpath('//*[contains(@class,"profile-degree")]/div[@class="title"]/text()').extract())
        item['score'] = DataFilter.simple_format(response.xpath('//span[starts-with(@class, "score-link")]').extract())

        top_coauthors = response.xpath('//div[starts-with(@class, "authors-block")]//ul/li//h5[@class="ga-top-coauthor-name"]/a')
        item['co_authors'] = parse_text_by_multi_content(top_coauthors, "|")
        
        skills_expertise = response.xpath('//div[starts-with(@class, "profile-skills")]/ul/li//a[starts-with(@class, "keyword-list-token-text")]')
        item['skills'] = parse_text_by_multi_content(skills_expertise, "|")

        topics = response.xpath('//ul[@class="keyword-list clearfix"]/li//a[starts-with(@class, "keyword-list-token-text")]')
        item['topics'] = parse_text_by_multi_content(topics, "|")

        item['institution'] = DataFilter.simple_format(response.xpath('//div[starts-with(@class, "institution-name")]').extract())
        item['department'] = DataFilter.simple_format(response.xpath('//div[@class = "institution-dept"]').extract())
        
        item['city'] = city
        item['province'] = province
        item['country'] = country

        # insert the url of this request into mongodb collection
        client = pymongo.MongoClient(
            "118.190.45.60",
            27017
        )

        db = client["RG_Chinese"]
        auth_result = db.authenticate(name='eol_spider', password='m~b4^Uurp)g', mechanism='SCRAM-SHA-1')
        collection = db['used_link']

        if collection.find_one({"_id" : person_key}):
            print "This url is already inserted into mongodb \n"
        else:
            collection.insert_one({'_id': person_key, 'value': response.url})
        client.close()

        # delete already used link from Redis
        conn = redis.Redis('127.0.0.1', 6379)
        conn.hdel('rg_chinese', person_key)
        print '---One url is deleted : %s : %s ---' %(person_key, response.url) 

        # client = pymongo.MongoClient(
        #     "118.190.45.60",
        #     27017
        # )
        # db = client["Research_Gate"]
        # collection = db['original_url']

        # collection.delete_many({'_id' : person_key})
        # client.close()


        if featured_researches and country != 'China': 
            url = response.url + "/publications"
            yield item
            yield Request(url, headers=headers, callback=self.parse_contribution, dont_filter=True, meta={"person_key":person_key})
        else:
            print "--------Nothing to return, it is invalid--------"

    def parse_contribution(self, response):
        if response.status == 429:
            # lostitem_str = 'lost contribution: ' + response.url
            # self.lostitem_file.write(lostitem_str)
            # self.lostitem_file.close()
            client = pymongo.MongoClient(
                "118.190.45.60",
                27017
            )
            db = client["RG_Chinese"]
            auth_result = db.authenticate(name='eol_spider', password='m~b4^Uurp)g', mechanism='SCRAM-SHA-1')
            collection = db['lost_url']
            collection.insert_one({'lost_usl':response.url, 'type':'contribution'})
            client.close()
            raise CloseSpider(reason=u'被封了，准备切换ip')


        headers = response.request.headers
        headers["referer"] = response.url
        # Parse articles, each article has a seperate page
        person_key = response.meta["person_key"]
        
        headers = response.request.headers
        headers["referer"] = response.url
        article_urls = response.xpath(
                '//li[contains(@class, "li-publication")]/descendant::a[contains(@class, "js-publication-title-link")]/@href').extract()
        for article_url in article_urls:
            article_url = self.domain + "/" + article_url
            yield Request(article_url, headers=headers, callback=self.parse_article, dont_filter=True, meta={'person_key':person_key})

    def parse_article(self, response):
        if response.status == 429:
            # lostitem_str = 'lost article: ' + response.url
            # self.lostitem_file.write(lostitem_str)
            # self.lostitem_file.close()
            client = pymongo.MongoClient(
                "118.190.45.60",
                27017
            )
            db = client["RG_Chinese"]
            auth_result = db.authenticate(name='eol_spider', password='m~b4^Uurp)g', mechanism='SCRAM-SHA-1')
            collection = db['lost_url']
            collection.insert_one({'lost_usl':response.url, 'type':'article'})
            client.close()
            raise CloseSpider(reason='被封了，准备切换ip')

        item = RGArticleItem()
        person_key = response.meta['person_key']
        item['author_key'] = person_key
        item['article_key'] = request_fingerprint(response.request)

        article_item = {}
        article_name = DataFilter.simple_format(response.xpath('//div[@class="publication-header"]//h1[@class="publication-title"]/text()').extract())
        article_item['article_name'] = article_name
        article_abstract = DataFilter.simple_format(response.xpath('//div[@class="publication-abstract"]/div[2]').extract())
        article_item['article_abstract'] = article_abstract
        article_journal = DataFilter.simple_format(response.xpath('//span[@class="publication-meta-journal"]/a').extract())
        article_date = DataFilter.simple_format(response.xpath('//span[@class="publication-meta-date"]').extract())
        article_item['article_journal'] = article_journal + ", " + article_date
        item['article'] = article_item
        return item
    
    def __init__(self, **kwargs):
        # self.lostitem_file = open('/data/pure_chinese_lost.out', 'a+')
        super(RGSpider1, self).__init__(**kwargs)
        pass

    def close(self, reason):
        # self.lostitem_file.close()
        super(RGSpider1, self).close(self, reason)
