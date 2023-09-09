import sys
from dataclasses import dataclass
from requests import get
from requests.exceptions import RequestException
from bs4 import BeautifulSoup
import re
import pandas as pd
from io import StringIO
from lxml.etree import XMLSyntaxError

# https://warframe.fandom.com/pt-br/wiki/Especial:Busca?query=prime&scope=internal&navigationSearch=true
    # div.unified-search__layout__main > p.unified-search__results__count - title
    # h3.unified-search__result__header > a.unified-search__result__title

# https://warframe.fandom.com/pt-br/wiki/Prime_Laser_Rifle
    # h1#firstHeading > span.mw-page-title-main - title
    # span#Aquisição - Content


@dataclass
class Page:
    url: str
    title: str
    content: str

    def print(self):
        print(f"titulo: {self.title}")
        print("-"*30)
        print(f"onde conseguir:")
        print('='*30)
        print(self.content)
        print('='*30)


@dataclass
class Website:
    name: str
    url: str
    title_tag: str
    content_tag: str

    def __add__(self, other):
        if isinstance(other, Page):
            return self.__join_urls(other.url)
        return self.__join_urls(str(other))
        
    
    def __join_urls(self, page_url: str):
        if self.url.endswith('/') and not page_url.startswith('/') or \
            not self.url.endswith('/') and page_url.startswith('/'):
            return f'{self.url}{page_url}'
        elif not self.url.endswith('/') and not page_url.startswith('/'):
            return f'{self.url}/{page_url}'
        else:
            return  f'{self.url}/{page_url[1:]}'


class RequestManagerMixin:
    def get_req(self, url):
        try:
            req = get(url)
        except RequestException:
            return
        return req
    def get_bs(self, url):
        req = self.get_req(url)
        if req is None:
            return
        return BeautifulSoup(req.text, 'html.parser')


class Crawler(RequestManagerMixin):
    def get_children(self, bs: BeautifulSoup, tag: str, get_list: bool = False, get_tags: bool = False):
        elems = bs.select(tag)
        if elems is None or len(elems) == 0:
            return ''
        if get_list:
            return elems
        if not get_tags:
            return ''.join([elem.get_text() for elem in elems])
        return ''.join([str(elem) for elem in elems])
    
    def get_title(self, bs, tag, is_search):
        title = self.get_children(bs, tag)

        if is_search:
            try:
                [title] = re.findall(r'[\w]*[\'"](.+)[\'"]', title)        
            except ValueError:
                pass

        return title
    
    def get_content(self, bs, tag, is_search):
        content = self.get_children(bs, tag, get_list=is_search)
        
        if is_search and content is not None:
            content = [
                re.sub(r"\s", "", elem.get_text())+' - '+elem.attrs["href"]
                for elem in content
            ]

        if not is_search and content == '':
            p_tag = 'div.wds-tab__content.wds-is-current h2~p'
            table_tag = 'div.wds-tab__content.wds-is-current>table.article-table'

            p_text = self.get_children(bs, p_tag, get_list=is_search)
            tables = self.get_children(bs, table_tag, get_list=is_search, get_tags=True)

            p_text = re.sub(r"[\s]+", " ", p_text)
            
            table_text = ''
            try:
                table_text = pd.read_html(StringIO(tables))[0]
            except ValueError:
                pass
            except XMLSyntaxError:
                pass

            content = f'{p_text}\n\n{table_text}'


        return content

    def parse(self, website: Website, page_url: str, is_search: bool = False):
        full_url = website + page_url
        bs = self.get_bs(full_url)
        if bs is None:
            print('erro na requisição')
            return
        page_title = self.get_title(bs, website.title_tag, is_search)
        page_content = self.get_content(bs, website.content_tag, is_search)

        if page_title != '' and str(page_content).strip() != '' and page_content != []:
            page = Page(page_url, page_title, page_content)
            if not is_search:
                page.print()
            else: 
                return page.content
        else:
            print('nenhum valor de aquisição encontrado')


def app(system_args):
    if len(system_args) != 2:
        raise ValueError(
            "uma variavel deve ser passada ao chamar o script.py"
        )

    WEBSITE_NAME = "Warframe Wiki"
    WEBSITE_URL = 'https://warframe.fandom.com/pt-br/'
    query = system_args[1]
    query_url = f'wiki/Especial:Busca?query={query}&scope=internal&navigationSearch=true'
    search_website = Website(
        WEBSITE_NAME, WEBSITE_URL,
        'div.unified-search__layout__main>p.unified-search__results__count',
        'h3.unified-search__result__header>a.unified-search__result__title'
    )

    print(f'query: {query}\n')
    crawler = Crawler()
    links: str = crawler.parse(
        search_website, query_url,
        is_search=True
    )

    if links is None:
        print("nenhum resultado com essa pesquisa")
        return

    hrefs = []
    for i, link_href in enumerate(links):
        link, href = link_href.split(' - ')
        print(f'[{i}] - {link}')
        hrefs.append(href)

    link_choosed = ""
    while 1:
        list_index = input("\nescolha um item da lista pelo numero: ")
        if not list_index.isnumeric():
            continue
        index = int(list_index)
        if index >= len(hrefs):
            continue
        [link_choosed] = re.findall(r'.+(\/wiki\/.+)', hrefs[index])
        break
    
    object_website = Website(
        WEBSITE_NAME, WEBSITE_URL, 
        'h1#firstHeading>span.mw-page-title-main',
        'div.mw-parser-output>ul'
    )        

    print()
    crawler.parse(object_website, link_choosed)


if __name__ == '__main__':
    try:
        app(sys.argv)
    except ValueError as e:
        print("ocorreu um erro:", e)
