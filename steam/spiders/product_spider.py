import logging
import re
from w3lib.url import canonicalize_url, url_query_cleaner

from scrapy.http import FormRequest
from scrapy.linkextractors import LinkExtractor
from scrapy.spiders import CrawlSpider, Rule

from ..items import ProductItem, ProductItemLoader

logger = logging.getLogger(__name__)


def load_product(response):
    """Load a ProductItem from the product page response."""
    loader = ProductItemLoader(item=ProductItem(), response=response)

    url = url_query_cleaner(response.url, ['snr'], remove=True)
    url = canonicalize_url(url)
    loader.add_value('url', url)

    found_id = re.findall('/app/(.*?)/', response.url)
    if found_id:
        id = found_id[0]
        reviews_url = f'http://steamcommunity.com/app/{id}/reviews/?browsefilter=mostrecent&p=1'
        loader.add_value('reviews_url', reviews_url)
        loader.add_value('id', id)

    # Publication details.
    loader.add_css('title', '.apphub_AppName ::text')
    dev = response.xpath('//div[@class="dev_row"]/div[@id="developers_list"]/a/text()').extract()
    loader.add_value('developer', dev)
    pub = response.xpath('//div[@class="dev_row"][2]/a/text()').extract()
    loader.add_value('publisher', pub)
    date = response.xpath('//div[@class="release_date"]/div[@class="date"]/text()').extract_first()
    loader.add_value('release_date', date)
    genres = response.xpath('(//div[@class="details_block"])[1]/a/text()').extract()
    loader.add_value('genres', genres)

    
    loader.add_css('specs', '.game_area_details_specs a ::text')
    loader.add_css('tags', 'a.app_tag::text')

    price = response.css('.game_purchase_price ::text').extract_first()
    if not price:
        price = response.css('.discount_original_price ::text').extract_first()
        loader.add_css('discount_price', '.discount_final_price ::text')
    loader.add_value('price', price)

    sentiment = response.css('.game_review_summary').xpath(
        '../*[@itemprop="description"]/text()').extract()
    loader.add_value('sentiment', sentiment)
    
    #All review count
    n_reviews = response.xpath('//label[@for="review_type_all"]/span/text()').get()
    if n_reviews==None:
        n_reviews='0'
    else:
        n_reviews = re.sub('[\(\,\)]','',n_reviews)
    loader.add_value('n_reviews', n_reviews)
    
    #Positive review count
    p_reviews = response.xpath('//label[@for="review_type_positive"]/span/text()').get()
    if p_reviews==None:
        p_reviews='0'
    else:
        p_reviews = re.sub('[\(\,\)]','',p_reviews)
    loader.add_value('p_reviews', p_reviews)
    
    #Negative review count
    m_reviews = response.xpath('//label[@for="review_type_negative"]/span/text()').get()
    if m_reviews==None:
        m_reviews='0'
    else:
        m_reviews = re.sub('[\(\,\)]','',m_reviews)
    loader.add_value('m_reviews', m_reviews)
    
    #Platforms (OS)
    platform0 = response.xpath('//div[@class="game_area_purchase_platform"]/span/@class').getall()
    platform1 = [re.sub('platform_img ','',item) for item in platform0]
    loader.add_value('platform', platform1)

    loader.add_xpath(
        'metascore',
        '//div[@id="game_area_metascore"]/div[contains(@class, "score")]/text()')

    early_access = response.css('.early_access_header')
    if early_access:
        loader.add_value('early_access', True)
    else:
        loader.add_value('early_access', False)

    return loader.load_item()


class ProductSpider(CrawlSpider):
    name = 'products'
    start_urls = ['http://store.steampowered.com/search/?sort_by=Released_DESC']

    allowed_domains = ['steampowered.com']

    rules = [
        Rule(LinkExtractor(
             allow='/app/(.+)/',
             restrict_css='#search_result_container'),
             callback='parse_product'),
        Rule(LinkExtractor(
             allow='page=(\d+)',
             restrict_css='.search_pagination_right'))
    ]

    def __init__(self, steam_id=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.steam_id = steam_id

    def start_requests(self):
        if self.steam_id:
            yield Request(f'http://store.steampowered.com/app/{self.steam_id}/',
                          callback=self.parse_product)
        else:
            yield from super().start_requests()

    def parse_product(self, response):
        # Circumvent age selection form.
        if '/agecheck/app' in response.url:
            logger.debug(f'Form-type age check triggered for {response.url}.')

            form = response.css('#agegate_box form')

            action = form.xpath('@action').extract_first()
            name = form.xpath('input/@name').extract_first()
            value = form.xpath('input/@value').extract_first()

            formdata = {
                name: value,
                'ageDay': '1',
                'ageMonth': '1',
                'ageYear': '1955'
            }

            yield FormRequest(
                url=action,
                method='POST',
                formdata=formdata,
                callback=self.parse_product
            )

        else:
            yield load_product(response)
