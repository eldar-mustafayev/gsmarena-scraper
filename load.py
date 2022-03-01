import yaml
import requests
import lxml.html

from pathlib import Path
from typing import Iterator
from lxml.objectify import ObjectifiedElement

from proxy import Proxies
from user_agents import UserAgents

BASE_URL = 'https://www.gsmarena.com/'
USERAGENTS = UserAgents()
PROXIES = Proxies()


def get_tree(url: str) -> ObjectifiedElement:
    # Retry until request was sucessful
    
    while True:
        try:
            headers = USERAGENTS.get()
            proxy = PROXIES.get()
            proxy = {"http": proxy, "https": proxy}

            response = requests.get(url, proxies=proxy, headers=headers, timeout=12, verify=True)

            return lxml.html.fromstring(response.text)

        # if the request is successful, no exception is raised
        except requests.exceptions.ProxyError:
            print("Proxy error, choosing a new proxy")
            PROXIES.remove()
        except requests.exceptions.Timeout:
            print("Timeout error, choosing a new proxy")
            PROXIES.remove()
        except requests.exceptions.SSLError:
            print("SSL error, choosing a new proxy")
            PROXIES.remove()
        except requests.exceptions.ConnectionError:
            print("Connection error, choosing a new proxy")
            PROXIES.remove()

def get_phone_brands(tree: ObjectifiedElement) -> Iterator[tuple[str, str]]:
    brand_names = {
        'Apple',
        'BlackBerry',
        'Google',
        'Honor',
        'HTC',
        'Huawei',
        'LG',
        'Nokia',
        'Meizu',
        'OnePlus',
        'Oppo',
        'Realme',
        'Samsung',
        'Sony',
        'Xiaomi',
        'ZTE'
    }

    tree.make_links_absolute(BASE_URL)

    for brand_elem in tree.xpath('//td/a'):
        brand_name = brand_elem.text
        if brand_name not in brand_names:
            continue

        brand_url = brand_elem.get('href')
        yield brand_name, brand_url


def get_brand_models(tree: ObjectifiedElement) -> Iterator[tuple[str, str]]:

    def get_pages(tree: ObjectifiedElement) -> Iterator[ObjectifiedElement]:
        tree.make_links_absolute(BASE_URL)
        page_urls = tree.xpath('//div[@class="nav-pages"]/a/@href')

        yield tree
        for url in page_urls:
            page = get_tree(url)
            yield page

    def get_models_frompage(tree: ObjectifiedElement) -> Iterator[tuple[str, str]]:
        tree.make_links_absolute(BASE_URL)

        phone_names = tree.xpath('//div[@class="makers"]/ul/li/a/strong/span/text()')
        phone_urls = tree.xpath('//div[@class="makers"]/ul/li/a/@href')

        phone_names = map(str, phone_names)
        phone_urls = map(str, phone_urls)

        return zip(phone_names, phone_urls)

    for page_tree in get_pages(tree):
        for model in get_models_frompage(page_tree):
            yield model


def fix_path(path: str) -> Path:
    return Path(__file__).parent.resolve() / Path(path)

def serialize(brand_name: str, model_name: str, model_tree: ObjectifiedElement) -> None:
    Path(f"./data/models/html/{brand_name}").mkdir(exist_ok=True)
    filepath = fix_path(f'./data/models/html/{brand_name}/{model_name}.html')
    with open(filepath, 'wb') as file:
        file.write(lxml.html.tostring(model_tree))

    print(f"Loaded {model_name}")

def get_scraped_data() -> dict[str, dict[str, list[str]]]:
    filepath = fix_path("./data/metadata/scraped.yml")
    with open(filepath, "r") as stream:
        scraped_data = yaml.load(stream, Loader=yaml.Loader)
        if scraped_data is None:
            scraped_data = {'brands': {}}

        return scraped_data

def set_scraped_data(scraped_data: dict[str, dict[str, list[str]]]):
    filepath = fix_path("./data/metadata/scraped.yml")
    with open(filepath, "w") as stream:
        yaml.dump(scraped_data, stream)


if __name__ == '__main__':
    scraped_models = get_scraped_data()
    main_tree = get_tree('https://www.gsmarena.com/makers.php3')
    for brand_name, brand_url in get_phone_brands(main_tree):

        if brand_name not in scraped_models['brands']:
            scraped_models['brands'][brand_name] = []

        brand_tree = get_tree(brand_url)
        for model_name, model_url in get_brand_models(brand_tree):

            if model_name in scraped_models['brands'][brand_name]:
                continue

            model_tree = get_tree(model_url)
            serialize(brand_name, model_name, model_tree)

            scraped_models['brands'][brand_name].append(model_name)
            set_scraped_data(scraped_models)
