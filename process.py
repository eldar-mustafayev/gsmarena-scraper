import os
import yaml
import lxml.html

from pathlib import Path
from typing import Iterator
from lxml.objectify import ObjectifiedElement

def unit(x: str):
    x = x.lower()
    if x == 'tb':
        return 1024 * 1024 * 1024
    elif x == 'gb':
        return 1024 * 1024
    elif x == 'mb':
        return 1024
    elif x == 'kb':
        return 1
    raise ValueError

def get_tree(html_path: Path) -> ObjectifiedElement:
    with open(html_path) as file:
        return lxml.html.fromstring(file.read())

def get_model_params(model_name: str, tree: ObjectifiedElement) -> dict[str, str]:

    def get_data_spec(name: str) -> str:
        value = tree.xpath(f'//*[@data-spec="{name}"]/text()')
        if len(value) != 1:
            print(f"Incorrect number of elements in {name} data spec, {model_name}")
            return "MISSING"
        return value[0]

    def get_sub_data_spec(name: str) -> str:
        sub_value = tree.xpath(f'//*[@data-spec="{name}"]/../span[2]/text()')
        if len(sub_value) != 1:
            print(f"Incorrect number of elements in {name} data spec, {model_name}")
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
        storages = sorted(storages, key=lambda x: int(x[:-2]) * unit(x[-2:]) if x != "MISSING" else -1)
        storages = ','.join(storages)

        rams = set(memory[1] for memory in memory_seperated)
        rams = sorted(rams, key=lambda x: int(x[:-2]) * unit(x[-2:]) if x != "MISSING" else -1)
        rams = ','.join(rams)

        return storages, rams

    def get_image() -> str:
        value = tree.xpath('//*[@class="specs-photo-main"]/a/img/@src')
        if len(value) != 1:
            print(f"Incorrect number of images, {model_name}")
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
    has_header = filepath.exists()

    with open(filepath, 'a') as file:
        if not has_header:
            file.write('|||'.join(model_param.keys()) + '\n')
            
        file.write('|||'.join(model_param.values()) + '\n')

def get_processed_data() -> dict[str, dict[str, list[str]]]:
    filepath = fix_path("./data/metadata/processed.yml")
    with open(filepath, "r") as stream:
        processed_data = yaml.load(stream, Loader=yaml.Loader)
        if processed_data is None:
            processed_data = {'brands': {}}

        return processed_data


def set_processed_data(processed_data: dict[str, dict[str, list[str]]]):
    filepath = fix_path("./data/metadata/processed.yml")
    with open(filepath, "w") as stream:
        yaml.dump(processed_data, stream)

if __name__ == "__main__":
    processed_models = get_processed_data()
    brands_dir = fix_path("./data/models/html")
    for model in brands_dir.glob("*/*.html"):
        
        brand_name = os.path.basename(model.parent)
        if brand_name not in processed_models['brands']:
             processed_models['brands'] = {brand_name: []}

        if model.name in processed_models['brands'][brand_name]:
            continue

        tree = get_tree(model)
        model_param = get_model_params(model.name, tree)
        serialize(brand_name, model_param)

        processed_models['brands'][brand_name].append(model.name)
        set_processed_data(processed_models)


