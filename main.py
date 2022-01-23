# from _typeshed import StrPath

import yaml
from pathlib import Path
from typing import Iterator

import lxml.html
import requests as requests
from lxml.objectify import ObjectifiedElement
from proxy import Proxies
from user_agents import UserAgents

BASE_URL = 'https://www.gsmarena.com/'
USERAGENTS = UserAgents()
PROXIES = Proxies()


def get_tree(url: str) -> ObjectifiedElement:
    headers = USERAGENTS.get()
    page = PROXIES.scrape(url, timeout=12, verify=True, headers=headers)
    while page.status_code == 429:  # add it to the proxy script
        print("Too many requests, choosing a new proxy")
        PROXIES.remove()

        page = PROXIES.scrape(url, timeout=12, verify=False)

    page.raise_for_status()

    return lxml.html.fromstring(page.text)


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
            yield get_tree(url)

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


def get_model_params(tree: ObjectifiedElement) -> dict[str, str]:
    def get_data_spec(name: str) -> str:
        value = tree.xpath(f'//*[@data-spec="{name}"]/text()')
        if len(value) != 1:
            print(f"Incorrect number of elements in {name} data spec, {model_url}")
            return "MISSING"
        return value[0]

    def get_sub_data_spec(name: str) -> str:
        sub_value = tree.xpath(f'//*[@data-spec="{name}"]/../span[2]/text()')
        if len(sub_value) != 1:
            print(f"Incorrect number of elements in {name} data spec, {model_url}")
            return "MISSING"
        return sub_value[0]

    def get_memory_spec() -> tuple[str, str]:
        internal_memory = get_data_spec('internalmemory')

        memory_list = internal_memory.split(',')
        memory_seperated = [
            memory.strip().split(' ')[:2]
            for memory in memory_list
        ]

        for i in range(len(memory_seperated)):
            memory = memory_seperated[i]
            for j in range(2):
                try:
                    if not memory[j]:
                        memory[j] = "MISSING"
                except IndexError:
                    memory.append("MISSING")

        storages = set(memory[0] for memory in memory_seperated)
        storages = ','.join(storages)

        rams = set(memory[1] for memory in memory_seperated)
        rams = ','.join(rams)

        return storages, rams

    def get_image() -> str:
        value = tree.xpath('//*[@class="specs-photo-main"]/a/img/@src')
        if len(value) != 1:
            print(f"Incorrect number of images, {model_url}")
            return "MISSING"
        return value[0]

    storage, ram = get_memory_spec()
    model_param = dict(
        model_name=get_data_spec('modelname'),
        release_date=get_data_spec('released-hl'),
        body=get_data_spec('body-hl'),
        os=get_data_spec('os-hl'),
        storage_prnt=get_data_spec('storage-hl'),
        display_size=get_data_spec('displaysize-hl'),
        resolution=get_data_spec('displayres-hl'),
        camera_pixel=get_data_spec('camerapixels-hl'),
        pixel_unit=get_sub_data_spec('camerapixels-hl'),
        video_pixel=get_data_spec('videopixels-hl'),
        ram_prnt=get_data_spec('ramsize-hl'),
        ram_unit=get_sub_data_spec('ramsize-hl'),
        chipset=get_data_spec('chipset-hl'),
        battery_size=get_data_spec('batsize-hl'),
        battery_unit=get_sub_data_spec('batsize-hl'),
        battery_type=get_data_spec('battype-hl'),
        sim_slots='2' if "dual" in get_data_spec('sim').lower() else '1',
        colors=get_data_spec('colors'),
        storage=storage,
        ram=ram,
        image=get_image(),
    )

    return model_param


def fix_path(path: str) -> Path:
    return Path(__file__).parent.resolve() / Path(path)


def serialize(brand_name: str, model_param: dict[str, str]) -> None:
    filepath = fix_path(f'./data/models/specs/{brand_name}.txt')
    with open(filepath, 'a') as file:
        file.write('|||'.join(model_param.values()))
        file.write('\n')


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
            model_param = get_model_params(model_tree)
            serialize(brand_name, model_param)

            scraped_models['brands'][brand_name].append(model_name)
            set_scraped_data(scraped_models)
