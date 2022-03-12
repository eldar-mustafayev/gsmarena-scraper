from datetime import datetime
import yaml
import threading
import requests
import lxml.html

from pathlib import Path
from dotenv import dotenv_values
from typing import Iterator, Optional
from lxml.objectify import ObjectifiedElement
from concurrent.futures import ThreadPoolExecutor, as_completed

lock = threading.Lock()
config = dotenv_values(".env")
BASE_URL = 'https://www.gsmarena.com/'

log_file = open(f'./output-{datetime.now()}.txt', 'w')
def printf(*args, **kwargs):
    with lock:
        print(*args, **kwargs, file=log_file, flush=True)

BATCH_SIZE = 10
THREAD_NUM = 4
MAX_RETRIES = 3

class TooManyRequests(requests.exceptions.RequestException): pass

def get_tree(url: str) -> Optional[ObjectifiedElement]:
    # Retry until request was sucessful
    
    for _ in range(MAX_RETRIES):
        try:
            params = {'api_key': config["API_KEY"], 'url': url}
            response = requests.get(
                'http://api.scraperapi.com',
                params=params,
                verify=False
            )
            if response.status_code == 200:
                return lxml.html.fromstring(response.text)
            elif response.status_code in [404, 410]:
                return None
            elif response.status_code == 500:
                printf("Timeout error, trying again")
            elif response.status_code == 429:
                printf("Too many requests, trying again")

        except requests.exceptions.ConnectionError:
            printf("Connection to the API failed, trying again")


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

    def get_pages(tree: ObjectifiedElement) -> Iterator[Optional[ObjectifiedElement]]:
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
        if page_tree is None:
            printf("Skipping brand page")
            continue

        for model in get_models_frompage(page_tree):
            yield model


def fix_path(path: str) -> Path:
    return Path(__file__).parent.resolve() / Path(path)


def serialize(brand_name: str, model_name: str, model_tree: ObjectifiedElement) -> None:

    Path(f'./data/models/html/{brand_name}').mkdir(exist_ok=True)

    model_name = model_name.replace('/', '|')
    filepath = fix_path(f'./data/models/html/{brand_name}/{model_name}.html')

    with open(filepath, 'wb') as file:
        file.write(lxml.html.tostring(model_tree))


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


def main():
    with ThreadPoolExecutor(THREAD_NUM) as pool:
        scraped_models = get_scraped_data()

        main_tree = get_tree('https://www.gsmarena.com/makers.php3')
        assert main_tree is not None

        for brand_name, brand_url in get_phone_brands(main_tree):

            if brand_name not in scraped_models['brands']:
                scraped_models['brands'][brand_name] = []

            brand_tree = get_tree(brand_url)
            if brand_tree is None:
                printf(f"Skipping {brand_name} brand")
                continue
            else:
                printf(f"Extracted {brand_name} brand")

            futures = {}
            for model_name, model_url in get_brand_models(brand_tree):

                if model_name in scraped_models['brands'][brand_name]:
                    continue

                future = pool.submit(get_tree, model_url)
                futures[future] = (model_name, model_url)
                if len(futures) < BATCH_SIZE:
                    continue

                for future in as_completed(futures):

                    model_tree = future.result()
                    model_name, model_url = futures[future]

                    if model_tree is None:
                        printf(f"Skipping {model_name} model")
                        continue
                    else:
                        printf(f"Extracted {model_name} model")
                    
                    serialize(brand_name, model_name, model_tree)

                    scraped_models['brands'][brand_name].append(model_name)
                    set_scraped_data(scraped_models)

                futures.clear()


if __name__ == '__main__':
    main()
