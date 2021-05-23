import json
from multiprocessing import Process, Queue
from math import ceil
from pathlib import Path
import random
import os
import tools.scripts.image_tools as it
from tools.scripts.ipfs_tools import upload_to_ipfs

PROCESSES=6

DEFAULT_PATH = Path('../../dogs/meta/metadata.json')
DEFAULT_TOKENS_STRUCTURE_PATH = Path('../structurev2')

EQUIPMENT_COUNT_ODDS = [
  (0, 5),
  (1, 20),
  (2, 60),
  (3, 120),
  (4, 160),
  (5, 120),
  (6, 50),
  (7, 15),
]

EQUIPMENT_DISTR = []

def save_doggies_json_to_db(db, delete_all=False):
    js = load_json_file()

    with db.cursor() as c:
        if delete_all:
            c.execute("DELETE FROM metadata_doggies WHERE 1=1;")
            db.commit()

        for dog in js:
            _body_721 = dog['721']
            policy = list(_body_721.keys())[0]
            _doggie_part = _body_721[policy]

            doggie_name = list(_doggie_part.keys())[0]

            _doggie_info = _doggie_part[doggie_name]

            doggie_id = _doggie_info['id']
            doggie_image = _doggie_info['image']

            c.execute("INSERT INTO metadata_doggies (doggie_id, doggie_metadata, doggie_image) VALUES (%s, %s, %s) ON CONFLICT (doggie_id) DO NOTHING;",
                    (doggie_id, json.dumps(dog), doggie_image))

    db.commit()



def get_decors_amount():
    global EQUIPMENT_DISTR
    if not EQUIPMENT_DISTR:
        for odd in EQUIPMENT_COUNT_ODDS:
            for _ in range(odd[1]):
                EQUIPMENT_DISTR.append(odd)

    odd = EQUIPMENT_DISTR[random.randint(0, len(EQUIPMENT_DISTR)-1)]
    return odd[0]

def replace_doggies(db):
    json_data = load_json_file()
    process_doggies_json(db, json_data, delete_previous=True)
    print("FINISHED")
    return True

def load_json_file(path_to_json=None):

    path_to_json = path_to_json or DEFAULT_PATH

    f_content = None
    with open(path_to_json, 'r') as f:
        f_content = f.read()

    js = json.loads(f_content)

    return js


def get_tier(index, tier=None):
    if isinstance(tier, int):
        return tier
    step_size = 1000
    return int(index/step_size)


def get_price(tier):
    price_tiers = [
            32 * 1000000,
            42 * 1000000,
            52 * 1000000,
            62 * 1000000,
            67 * 1000000,
            72 * 1000000,
            77 * 1000000,
            82 * 1000000,
            87 * 1000000,
            92 * 1000000,
            97 * 1000000,
            ]

    return price_tiers[tier]


prices_hash = dict()
def derive_price(index, tier=None, ignore_hash=False):
    global prices_hash

    randomness = 2 * 1000000
    tier = tier or get_tier(index)

    while True:
        random_extra = random.randint(100,randomness)
        value = get_price(tier) + random_extra
        if not (str(value) in prices_hash) or ignore_hash:
            break
        print(f"Tried {value} already used previously")
    prices_hash[str(value)]=True
    return value


def process_doggies_json(db, js, delete_previous=False):
    iterator = 0
    amount = len(js)
    minting_id = 1

    with db.cursor() as c:
        if delete_previous:
            c.execute("DELETE FROM doggies WHERE 1=1;")
            db.commit()
        else:
            # Get latest minting ID
            c.execute("SELECT MAX(minting_id) FROM doggies;")
            max_id, = c.fetchone()
            if max_id:
                minting_id = max_id
        # Randomize order
        for dog in random.sample(js,amount):
            _body_721 = dog['721']
            # Get Policy
            policy = list(_body_721.keys())[0]

            _doggie_part = _body_721[policy]

            doggie_name = list(_doggie_part.keys())[0]

            _doggie_info = _doggie_part[doggie_name]

            doggie_id = _doggie_info['id']
            doggie_image = _doggie_info['image']

            price = derive_price(iterator)
            tier = get_tier(iterator)


            c.execute("INSERT INTO doggies (minting_id, price, doggie_id, doggie_metadata, doggie_image, tier) VALUES (%s, %s, %s, %s, %s, %s);",
                    (minting_id, price, doggie_id, json.dumps(dog), doggie_image, tier))

            print(f'{doggie_id} - {doggie_name} for {price}. Hash = {policy}. image = {doggie_image}')
            iterator += 1
            minting_id += 1
            if not (iterator % 100):
                db.commit()

    db.commit()

def get_meta(path: Path):
    # Get some meta data from the file.
    # We use: X_filename_Y
    # Where X = probability
    # Y = layer priority. Highest goes last
    # Returns: (Name, Probability, Layer)
    file_name = path.stem
    splits = file_name.split('_')
    probability = None
    layer = None
    try:
        probability = int(splits[0])
    except Exception:
        # This is not an int then
        pass
    try:
        layer = int(splits[-1])
    except Exception:
        # This is not an int then
        pass
    if not (probability is None):
        del splits[0]
    if not (layer is None):
        del splits[-1]

    return ('_'.join(splits), probability, layer)

"""
Structure:
    dogs:
        breed:
            dog body
            decorations (items) specific to the dog
    decorations:
        backgrounds
        items
"""
class Variant(object):
    # Basic component of a dog - the png piece itself
    file_path: Path
    name: str
    probability: int
    layer = None
    category = None

    def __init__(self, path, cat, parent_layer=None):
        self.category = cat
        self.file_path = path
        name, prob, layer = get_meta(path)
        self.name = name
        self.probability = prob
        self.layer = layer or parent_layer

    def __repr__(self):
        return f'Variant({self.name},{self.probability})'

    def __str__(self):
        return f'{self.name}'

    def __lt__(self, other):
        return self.layer < other.layer


REQUIRED_DECORS = ('background', 'background_shadow')

class Category(object):
    name: str
    variants: list # Comp
    layer: int
    file_path: Path
    breed_specific: bool
    variants_distr: list
    is_body = False

    def __str__(self):
        return f'{self.name}'

    def setup_variants_distr(self):
        self.variants_distr = []
        for variant in self.variants:
            for i in range(variant.probability):
                self.variants_distr.append(variant)

    def get_random_variant(self):
        return self.variants_distr[random.randint(0, len(self.variants_distr)-1)]


class DecorCategory(Category):
    probability: int
    is_required: bool

    def __init__(self, cat_path: Path, breed_specific: bool):
        self.file_path = cat_path
        self.breed_specific = breed_specific

        cat_name, probability, layer = get_meta(cat_path)

        self.is_required = cat_name in REQUIRED_DECORS
        self.probability = probability
        self.name = cat_name
        self.layer = layer

        variants = list()
        variants_paths = [variant for variant in cat_path.iterdir() if variant.is_file()]
        for var_path in variants_paths:
            variant = Variant(var_path, self, layer)
            variants.append(variant)

        self.variants = variants

        self.setup_variants_distr()

    def __repr__(self):
        return f'DecorCategory({self.name}, {self.probability})'

class BodyComp(Category):
    def __init__(self, comp_path: Path):
        self.file_path = comp_path
        self.is_body = True

        comp_name, probability, layer = get_meta(comp_path)

        self.name = comp_name
        self.layer = layer

        variants = list()
        variants_paths = [variant for variant in comp_path.iterdir() if variant.is_file()]
        for var_path in variants_paths:
            variant = Variant(var_path, self, layer)
            variants.append(variant)

        self.variants = variants
        self.setup_variants_distr()

    def __repr__(self):
        return f'BodyComp({self.name})'

class Breed(object):
    name: str
    body_components: list
    decorations: list

    decors_distribution: list

    probability: int
    file_path: Path

    def __init__(self, breed_path: Path):
        self.file_path = breed_path

        name, probability, _ = get_meta(breed_path)

        self.probability = probability
        self.name = name

        self.body_components = []
        self.decorations = []

        inner_folders = [folder for folder in breed_path.iterdir() if folder.is_dir()]
        for folder in inner_folders:
            if 'decoration' in folder.name:
                self.decorations = get_decor_cats(folder, breed_specific=True)
            else:
                self.body_components.append(BodyComp(folder))

    def init_decorations(self, generic_decorations):
        self.decors_distribution = []
        self.decorations.extend(generic_decorations)

        # Compute distribution
        for decoration in self.decorations:
            if decoration.is_required:
                continue # Required are not rolled
            for i in range(decoration.probability):
                self.decors_distribution.append(decoration)

    def __str__(self):
        return f'{self.name}'
    def __repr__(self):
        return f'Breed({self.name}, {self.probability})'

class Rule(object):
    parent = None
    def __init__(self, parent):
        self.parent = parent
    def apply(self, dog):
        return True
    def check_cat(self, cat):
        return True # True means valid
    def check_variant(self, variant):
        return True # True means valid
    def is_allowed(self, dog):
        # Is a loose rule
        # Post-processing will do 'apply' anyway, even if is_allowed is True
        # Is good to enforce pre-processing
        return True
    def morph(self, dog):
        return False

class RuleMorph(Rule):
    target_variant = None
    morph_variant = None
    def __init__(self, parent, target_variant, morph_variant):
        self.target_variant = target_variant
        self.morph_variant = morph_variant
        super().__init__(parent)
    def morph(self, dog):
        print(f"Morphed from {self.target_variant} to {self.morph_variant}")
        for decor in dog.decorations:
            if decor == self.target_variant:
                dog.decorations.remove(decor)
                dog.decorations.append(self.morph_variant)
                return True
        return False


class RuleMultiple(Rule):
    rules: list
    def __init__(self, parent, rules):
        self.rules = rules
        super().__init__(parent)

    def apply(self, dog):
        for rule in self.rules:
            rule.apply(dog)

    def check_cat(self, cat):
        for rule in self.rules:
            if not rule.check_cat(cat):
                return False
        return True

    def check_variant(self, variant):
        for rule in self.rules:
            if not rule.check_variant(variant):
                return False
        return True

    def is_allowed(self, dog):
        for rule in self.rules:
            if not rule.is_allowed(dog):
                return False
        return True

    def morph(self, dog):
        morphed = False
        for rule in self.rules:
            if rule.morph(dog):
                morphed = True
        return morphed

class RuleNoVariant(Rule):
    blaclisted_variants = None
    def __init__(self, parent, variants):
        self.blacklisted_variants = variants

        super().__init__(parent)

    def apply(self, dog):
        for part in dog.decorations:
            if not self.check_variant(part):
                dog.remove_item(part, body_part=False)

    def check_variant(self, variant):
        if variant.name in self.blacklisted_variants:
            return False
        return True



class RuleNoCategory(Rule):
    blacklisted_cats = None
    def __init__(self, parent, cats_list):
        self.blacklisted_cats = cats_list

        super().__init__(parent)

    def apply(self, dog):
        for part in dog.body_parts:
            if not self.check_cat(part.category):
                dog.remove_item(part, body_part=True)
        for part in dog.decorations:
            if not self.check_cat(part.category):
                dog.remove_item(part, body_part=False)

    def check_cat(self, cat):
        if cat.name in self.blacklisted_cats:

            if (cat.name == 'head') and cat.is_body:
                # Stupid exception because we called "head" a body part and "head" decoration category
                return True
            if (cat.name == 'body') and cat.is_body:
                # Another exception...
                return True

            return False
        return True

class RuleMaskDoberman(Rule):
    def __init__(self, parent):
        super().__init__(parent)
    def apply(self, dog):
        if dog.breed.name == 'doberman':
            for part in dog.body_parts:
                if part.category.name == 'mouth':
                    dog.remove_item(part, body_part=True)

def get_rule(breed, variant):
    category = variant.category

    # Eyes: some eyes have smiles. remove mouth for them
    if category.name == 'eyes':
        if variant.name in ['angry', 'hypnosis', 'surprised']:
            return RuleNoCategory(variant, ['mouth'])
    if (category.name == 'head') and not category.is_body:
        return RuleNoCategory(variant, ['hat'])
    if (category.name == 'hat'):
        return RuleNoCategory(variant, ['head'])

    if (category.name == 'body') and (variant.name == 'ninja'):
        # Ninja
        return RuleMultiple(variant, [RuleNoCategory(variant, ['arced_hand_wrist', 'feet', 'body_top', 'legs']),
                RuleMorph(variant, find_variant(breed, 'guitar'), find_variant(breed, 'guitar_for_ninja'))])

    if (category.name == 'arced_hand') and ('guitar' in variant.name):
        return RuleNoCategory(variant, ['straight_hand'])

    if category.name == 'mask':
        return RuleMaskDoberman(variant)

    if variant.name in ['handkerchief', 'scarf']:
        return RuleNoVariant(variant, ['bag_purple', 'bag_red', 'bag_yellow'])

    if category.name == 'body' and ('hoodie' in variant.name
                                    or 'acket' in variant.name
                                    or variant.name.startswith('shirt')):
        return RuleMultiple(variant, [RuleNoVariant(variant, ['bracelet', 'watch']),
                                      RuleMorph(variant, find_variant(breed, 'vest_tshirt'), find_variant(breed, 'vest_other'))]
                            )

    if category.name == 'arced_hand' and ('hoodie' in variant.name):
        return RuleNoCategory(variant, ['body', 'body_top'])

    if category.name == 'straight_hand' and ('flag' in variant.name):
        return RuleNoVariant(variant, ['umbrella_green', 'umbrella_red'])

    return None

def find_variant(breed, variant_name, category_name=None):
    for cat in breed.decorations:
        if category_name:
            if cat.name != category_name:
                continue
        for var in cat.variants:
            if var.name == variant_name:
                return var
    return None

def to_dict(variants_list):
    str_variants = []
    for variant in variants_list:
        str_variants.append({variant.category.name: variant.name})
    return str_variants

class Dog(object):
    breed = None

    body_parts: list
    decorations: list
    required_decorations: list

    dog_id = None

    rules: list

    def __init__(self,breed, manual=False):
        self.breed = breed
        self.rules = []

        self.body_parts = []
        self.decorations = []
        self.required_decorations = []

        if not manual:
            self.set_random_required_decorations()
            self.set_random_body()
            self.set_random_decorations()

            self.run_rules()

    def run_rules(self):
        self.rules_apply() # Final time just in case
        self.rules_morph() # Morph some elements
        self.rules_apply() # Just in case if morphing created new exceptions

    def rules_morph(self):
        for rule in self.rules:
            rule.morph(self)

    def set_random_body(self):
        for body_comp in self.breed.body_components:
            variant = body_comp.get_random_variant()
            self.add_item(variant, body_part=True)

        # Post processing
        self.rules_apply()

        return self.body_parts

    def set_random_required_decorations(self):
        for decor_cat in self.breed.decorations:
            if decor_cat.is_required and not decor_cat.is_body:
                self.required_decorations.append(decor_cat.get_random_variant())

    def rules_apply(self):
        for rule in self.rules:
            rule.apply(self)

    def rules_check_cat(self, cat):
        for rule in self.rules:
            if not rule.check_cat(cat):
                return False
        return True

    def rules_check_variant(self, variant):
        for rule in self.rules:
            if not rule.check_variant(variant):
                return False
        return True

    def add_item(self, item, body_part=False):
        new_rule = get_rule(self.breed, item)
        if new_rule:
            self.rules.append(new_rule)
        if body_part:
            self.body_parts.append(item)
        else:
            self.decorations.append(item)

    def remove_item(self, item, body_part=False):
        if body_part:
            self.body_parts.remove(item)
        else:
            self.decorations.remove(item)

        # Clean up rules of deleted elements
        for rule in self.rules:
            if rule.parent == item:
                self.rules.remove(rule)

    def get_random_decoration(self):
        while True:
            decor_cat = self.breed.decors_distribution[random.randint(0, len(self.breed.decors_distribution)-1)]

            # Do not repeat cats
            is_repeated=False
            for variant in self.decorations:
                if variant.category == decor_cat:
                    is_repeated=True
                    break
            if is_repeated:
                continue

            # Rules
            if not self.rules_check_cat(decor_cat):
                print(f"Skipping Category {decor_cat} due to rule")
                continue
            variant = decor_cat.get_random_variant()
            variant_rule = get_rule(self.breed, variant)
            if variant_rule and (not variant_rule.is_allowed(self)):
                # This variant doesn't like our dog
                print(f"Skipping variant {variant} because Rule does not permit this dog")
                continue

            if not self.rules_check_variant(variant):
               # This variant is not allowed by our existing rules
               print(f"Skipping variant {variant} because our Dog rules rejected it")
               continue

            return variant

    def set_random_decorations(self):
        decors_amount = get_decors_amount()

        while len(self.decorations) < decors_amount:
            decor = self.get_random_decoration()
            self.add_item(decor)

            self.rules_apply()

    def to_dict(self):
        breed = None

        dog_dict = {'dog_id': self.dog_id,
                    'breed': self.breed.name,
                    'body': to_dict(self.body_parts),
                    'setting': to_dict(self.required_decorations),
                    'traits': to_dict(self.decorations)}

        return dog_dict

    def make_image(self, path):
        all_layers = self.body_parts + self.decorations + self.required_decorations

        sorted_layers = sorted(all_layers)

        with it.load_layer(sorted_layers[0].file_path) as base_layer:
            for layer in sorted_layers[1:]:
                with it.load_layer(layer.file_path) as next_layer:
                    it.merge_layers(base_layer, next_layer)

            base_layer.save(Path(path))

        print(sorted_layers)

    def __repr__(self):
        return f'Dog({self.breed.name}, Body: {self.body_parts}, Decorations: {self.decorations}, Required: {self.required_decorations})'

    def __eq__(self, other):
        if self.breed.name != other.breed.name:
            return False
        if len(self.body_parts) != len(other.body_parts):
            return False
        if len(self.decorations) != len(other.decorations):
            return False
        # Let's not include background into unique
        #if len(self.required_decorations) != len(other.required_decorations):
            #return False
        for body_part in other.body_parts:
            if not (body_part in self.body_parts):
                return False
        for decor in other.decorations:
            if not (decor in self.decorations):
                return False
        #for decor in other.required_decorations:
            #if not (decor in self.required_decorations):
                #return False

        return True


class RootStructure(object):
    breeds : list
    decorations: list
    breeds_distribution: list

    def __init__(self, breeds, decorations):
        self.decorations = decorations
        self.breeds = breeds

        # Generate random breeds info
        self.breeds_distribution = list()
        for breed in breeds:
            for i in range(breed.probability):
                self.breeds_distribution.append(breed)

        # Compute decorations distribution for each breed
        for breed in breeds:
            breed.init_decorations(decorations)

    def get_random_breed(self, breeds_override):
        if breeds_override:
            while True:
                selected_breed =  self.breeds_distribution[random.randint(0, len(self.breeds_distribution)-1)]
                if selected_breed in breeds_override:
                    return selected_breed

        return self.breeds_distribution[random.randint(0, len(self.breeds_distribution)-1)]

    def load_dog(self, dog_dict):
        breed = None
        for b in self.breeds:
            if b.name == dog_dict['breed']:
                breed = b
                break
        dog = Dog(breed, manual=True)
        dog.dog_id = dog_dict['dog_id']
        for cat in dog_dict['body']:
            cat_name = list(cat.keys())[0]
            category = None
            for c in breed.body_components:
                if c.name == cat_name:
                    category = c
                    break

            variant_name = cat[cat_name]
            print(f"SEARCHING FOR {variant_name}")
            variant = None
            for v in category.variants:
                if v.name == variant_name:
                    variant = v
                    break
            assert variant
            dog.body_parts.append(variant)
        for cat in dog_dict['setting']:
            cat_name = list(cat.keys())[0]
            category = None
            for c in breed.decorations:
                if c.name == cat_name:
                    category = c
                    break

            variant_name = cat[cat_name]
            print(f"SEARCHING FOR {variant_name}")
            variant = None
            for v in category.variants:
                if v.name == variant_name:
                    variant = v
                    break
            assert variant
            dog.required_decorations.append(variant)
        for cat in dog_dict['traits']:
            cat_name = list(cat.keys())[0]
            category = None
            for c in breed.decorations:
                if c.name == cat_name:
                    category = c
                    break

            variant_name = cat[cat_name]
            print(f"SEARCHING FOR {variant_name}")
            variant = None
            for v in category.variants:
                if v.name == variant_name:
                    variant = v
                    break
            assert variant
            dog.decorations.append(variant)

        return dog


def get_decor_cats(decors_path, breed_specific=False):
    cats = [cat for cat in decors_path.iterdir() if cat.is_dir()]
    decor_cats = []
    for cat in cats:
        decor_cats.append(DecorCategory(cat, breed_specific))
    return decor_cats


def read_dogs_structure(structure_path=None):
    structure_path = structure_path or DEFAULT_TOKENS_STRUCTURE_PATH
    structure_path = Path(structure_path)

    decors_path = Path(structure_path / 'decoration')
    decor_cats = get_decor_cats(decors_path)
    breeds = []
    breeds_path = Path(structure_path / 'dog')
    breed_paths = [breed for breed in breeds_path.iterdir() if breed.is_dir()]

    for breed_path in breed_paths:
        breeds.append(Breed(breed_path))

    root = RootStructure(breeds, decor_cats)
    return root


def generate_random_dog(root, breeds_override):
    breed = root.get_random_breed(breeds_override)
    return Dog(breed)

def generate_unique_dogs(root, amount, dogs=None, dog_ids=None, breeds_override=None):
    dogs = dogs or []
    for i in range(amount):
        dog_id = i+1
        if dog_ids:
            dog_id = dog_ids[i]
        while True:
            dog = generate_random_dog(root, breeds_override)
            if not (dog in dogs):
                break
            print("Duplicate dog, trying again")
        dog.dog_id=dog_id
        dogs.append(dog)
    return dogs

def save_dogs_to_json(dogs, path=Path('../../dogs/json/dogs.json')):
    dogs_list = [dog.to_dict() for dog in dogs]
    with open(path, 'w') as f:
        f.write(json.dumps(dogs_list))

def load_dogs_from_json(root, path='../../dogs/json/dogs.json'):
    dogs = []
    with open(Path(path), 'r') as f:

        dogs_list = json.loads(f.read())

    for dog_dict in dogs_list:
        dogs.append(root.load_dog(dog_dict))

    return dogs


def ray_images(dogs, folder):
    for dog in dogs:
        dog_image_path = folder / f'doggie_{dog.dog_id}.png'
        dog.make_image(dog_image_path)



def create_images(dogs, folder=Path('../../dogs/images')):
    step = ceil(len(dogs) / PROCESSES)

    processes = []
    for i in range(PROCESSES):
        block = dogs[step*i:step*(i+1)]
        p = Process(target=ray_images, args=(block, folder))
        p.start()
        processes.append(p)

    for p in processes:
        p.join()
    print("Finished")

def get_image_url(dog_id, path):
    dog_path = path / f'doggie_{dog_id}.txt'
    url = None
    with open(dog_path, 'r') as f:
        url = f.read().strip()
    return url


def create_meta(dogs, path=Path('../../dogs/meta/metadata.json'), upl_path=Path('../../dogs/uploads')):
    import cli # Needed to load policy hash
    import constants

    json_obj = dict()
    dogs_json = []
    for dog in dogs:
        img_path = get_image_url(dog.dog_id, upl_path)
        dog_json =  {
            '721': {
                constants.POLICY_HASH:    {
                    f'CryptoDoggie{dog.dog_id}': {
                        'id': dog.dog_id,
                        'name': f'Crypto Doggie #{dog.dog_id}',
                        'image': f'ipfs://ipfs/{img_path}',
                        'breed': dog.breed.name,
                        'composition': dog.to_dict(),
                    }
                }
            }
        }
        dogs_json.append(dog_json)
    with open(path, 'w') as f:
        f.write(json.dumps(dogs_json))

def ray_upload_images(images, upl_folder):
    for img in images:
        print(f"uploading {img.stem}")
        url = upload_to_ipfs(img)
        with open(upl_folder / f"{img.stem}.txt", "w") as f:
            f.write(url)


def upload_images(img_folder=Path('../../dogs/images'), upl_folder=Path('../../dogs/uploads')):
    imgs = [img for img in img_folder.iterdir() if img.is_file()]
    uploads = [upl for upl in upl_folder.iterdir() if upl.is_file()]
    already_uploaded = []
    for upl in uploads:
        file_name = upl.stem
        already_uploaded.append(file_name)

    needs_uploading = []
    for img in imgs:
        if img.stem in already_uploaded:
            print(f"skipping {img.stem} - already uploaded")
            continue
        needs_uploading.append(img)

    step = ceil(len(needs_uploading) / PROCESSES)

    processes = []
    for i in range(PROCESSES):
        block = needs_uploading[step*i:step*(i+1)]
        p = Process(target=ray_upload_images, args=(block, upl_folder))
        p.start()
        processes.append(p)

    for p in processes:
        p.join()
    print("Finished")


def dogs_generator(amount):
    # Wraps it nicely
    r = read_dogs_structure()
    dogs = generate_unique_dogs(r, amount)
    save_dogs_to_json(dogs)
    create_images(dogs)
    upload_images()
    create_meta(dogs)


def create_dogs(from_id, to_id, folder):
    # Eh, probably not a good idea to use this directly - too slow

    r = read_dogs_structure()
    dogs = []
    image_urls = []
    for dog_id in range(from_id, to_id+1):
        while True:
            dog = generate_random_dog(r)
            if not (dog in dogs):
                break
            print("Duplicate dog, trying again")
        dogs.append(dog)
        dog_image_path = Path(folder) / f'doggie_{dog_id}.png'
        dog.make_image(dog_image_path)

        image_url = upload_to_ipfs(dog_image_path)

        image_urls.append(image_url)
        print(image_url)


