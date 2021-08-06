import xml.etree.ElementTree as ET
import bisect
import sqlite3
import os

import psycopg2


# simple in-memory index using binary search for key lookup
# probably implemented in std lib but I was too lazy to find...
class Index:
    def __init__(self):
        self.keys = []
        self.values = []
    
    def insert(self, key, value):
        idx = bisect.bisect_left(self.keys, key)
        self.keys.insert(idx, key)
        self.values.insert(idx, value)
    
    def find(self, key):
        idx = bisect.bisect_left(self.keys, key)
        if idx < len(self.keys):
            if self.keys[idx] == key:
                return self.values[idx]

    def find_all(self, key):
        found = []
        idx = bisect.bisect_left(self.keys, key)
        if idx < len(self.keys):
            while self.keys[idx] == key:
                found.append(self.values[idx])
                idx += 1
        return found


def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

print('Parsing OSM XML...')
tree = ET.parse('export.osm')
root = tree.getroot()

print('Indexing OSM buildings...')
# create index osm_id => tree_node
# osm has different id spaces for nodes, ways and relations, therefore use tuples (1st_tag_char, id) as ids
index_by_id = Index()
# create index (street_name, house_number) => tree_node
# lower() address strings
index_by_address = Index()
associated_street_relations = []
for element in root:
    if 'id' not in element.attrib:
        continue
    index_by_id.insert((element.tag[0], int(element.attrib['id'])), element)
    for element_child in element:
        if element_child.tag == 'tag':
            tag = element_child
            if (element.tag == 'way' or element.tag == 'relation') and tag.attrib['k'] == 'building':
                # element is building
                # TODO "node buildings"
                address = (None, None)
                for element_child in element:
                    if element_child.tag == 'tag':
                        tag = element_child
                        if address[0] is None and tag.attrib['k'] == 'addr:street':
                            address = (tag.attrib['v'].lower(), address[1])
                        elif address[1] is None and tag.attrib['k'] == 'addr:housenumber':
                            address = (address[0], tag.attrib['v'].lower())
                if address[0] is not None and address[1] is not None:
                    index_by_address.insert(address, element)
                break
            elif element.tag == 'relation' and tag.attrib['k'] == 'type' and tag.attrib['v'] == 'associatedStreet':
                # element is relation of type associatedStreet
                # there's no guarantee that referenced street and houses were already met and indexed, so these will need separate pass
                associated_street_relations.append(element)
                break
# TODO handle inconsistency if building has both street tag and street association with different streets
for element in associated_street_relations:
    houses = []
    street_name = None
    for element_child in element:
        if element_child.tag=='member' and element_child.attrib['role']=='house':
            houses.append(index_by_id.find((element_child.attrib['type'][0], int(element_child.attrib['ref']))))
        elif element_child.tag=='tag' and element_child.attrib['k']=='name': # assume that every associatedStreet relation has 'name' tag
            street_name = element_child.attrib['v']
    for house in houses:
        house_number = None
        for element_child in house:
            if element_child.tag=='tag' and element_child.attrib['k']=='addr:housenumber':
                house_number = element_child.attrib['v']
                break
        if house_number is None:
            continue
        index_by_address.insert((street_name.lower(), house_number.lower()), house)

#for idx, address in enumerate(index_by_address.keys):
#    print(address, ET.tostring(index_by_address.values[idx], encoding='unicode'))
#    #print(address, index_by_address.values[idx].attrib['id'])
#exit()

colors = {
    'red': '\u001b[31m',
    'green': '\u001b[32m',
    'orange': '\u001b[34m',
    'reset': '\u001b[0m'
}
#colors = {}

def log(street_name, building_number, domofoto_buildings=[], osm_buildings=[]):
    # df_buildings_n:0/1/M osm_buildings_n:0/1/M df_year:Y/N ...
    print('df_buildings_n:'+(colors.get('red', '')+'0' if not domofoto_buildings else colors.get('green', '')+'1' if len(domofoto_buildings)==1 else colors.get('orange', '')+'M')+colors.get('reset', '')+' osm_buildings_n:'+(colors.get('red', '')+'0' if not osm_buildings else colors.get('green', '')+'1' if len(osm_buildings)==1 else colors.get('orange', '')+'M')+colors.get('reset', '')+' df_year:?'+' addr:'+str((street_name, building_number))+' df_buildings:'+str([domofoto_building['id'] for domofoto_building in domofoto_buildings])+' osm_buildings:'+str([(osm_building.tag[0], int(osm_building.attrib['id'])) for osm_building in osm_buildings]))

# fix some diverged street names
streets_fix = {
 'М\'ясоєдовська вулиця': 'М’ясоєдовська вулиця',
 'Проспект Гагаріна': 'Гагаріна проспект',
 'Проспект Гагарина': 'Гагаріна проспект',
 'Івана і Юрія Лип вулиця': 'Івана та Юрія Лип вулиця',
}

print('Binding Domofoto and OSM buildings...')
df_con = sqlite3.connect('domfoto.db')
df_con.row_factory = dict_factory
df_cur = df_con.cursor()
addresses = list(df_cur.execute('SELECT DISTINCT street_id, streets.name, number FROM addresses JOIN streets ON streets.id=addresses.street_id WHERE number IS NOT NULL AND number != "" AND number != "(?)" AND building_id IS NOT NULL ORDER BY streets.name, addresses.number'))
index_by_df_building_ids = Index()
index_by_osm_building_ids = Index()
for address in addresses:
    address['name'] = streets_fix.get(address['name'], address['name'])
    # seems like only following current_state values are considered "actual"
    domofoto_buildings = list(df_cur.execute('SELECT * FROM buildings WHERE id in (SELECT building_id FROM addresses WHERE street_id=? AND number=?) AND current_state IN (" Используется ", " Строится ", " На реконструкции ", " Не используется (заброшено) ")', (address['street_id'], address['number'])))
    if not domofoto_buildings:
        log(address['name'], address['number'])
        continue
    osm_buildings = index_by_address.find_all((address['name'].lower(), address['number'].lower()))
    # TODO avoid adding duplicates at index build time
    osm_buildings = list(set(osm_buildings))
    # we don't skip bindings with empty osm building lists because they may cause clotting of other bindings with non-empty osm building lists
    #if not osm_buildings:
    #    log(address['name'], address['number'], domofoto_buildings)
    #    continue
    log(address['name'], address['number'], domofoto_buildings, osm_buildings)
    # CLOTTING
    # problem: even if single DF building found, it may have more DF addresses, which may link it to more OSM buildings, which may be also linked with other DF buildings...
    domofoto_building_ids = [df_building['id'] for df_building in domofoto_buildings]
    osm_building_ids = [(osm_building.tag[0], int(osm_building.attrib['id'])) for osm_building in osm_buildings]
    binding = (domofoto_building_ids, [(address['name'], address['number'])], osm_building_ids)
    for df_building_id in domofoto_building_ids:
        other_binding = index_by_df_building_ids.find(df_building_id)
        if other_binding is not None and other_binding is not binding:
            # merge
            # joining two lists of tuples of ints and strs: verified to work
            binding = (list(set(binding[0]+other_binding[0])), list(set(binding[1]+other_binding[1])), list(set(binding[2]+other_binding[2])))
    for osm_building_id in osm_building_ids:
        other_binding = index_by_osm_building_ids.find(osm_building_id)
        if other_binding is not None and other_binding is not binding:
            # merge
            binding = (list(set(binding[0]+other_binding[0])), list(set(binding[1]+other_binding[1])), list(set(binding[2]+other_binding[2])))
    # update index
    # TODO use binary search
    for df_building_id in binding[0]:
        try:
            idx = index_by_df_building_ids.keys.index(df_building_id)
            index_by_df_building_ids.values[idx] = binding
        except ValueError:
            index_by_df_building_ids.insert(df_building_id, binding)
    for osm_building_id in binding[2]:
        try:
            idx = index_by_osm_building_ids.keys.index(osm_building_id)
            index_by_osm_building_ids.values[idx] = binding
        except ValueError:
            index_by_osm_building_ids.insert(osm_building_id, binding)

# TODO list all df streets which have df buildings but no osm buildings found (possibly divergent street name)

def get_year(year):
    # 1961
    # 04.1961
    # 196x
    # 1960-е гг.
    # TODO 196s?
    if isinstance(year, str):
        if year.isdigit():
            return int(year)
        elif year[0:2].isdigit() and year[2]=='.' and year[3:].isdigit():
            return int(year[3:])
        elif year[:-1].isdigit() and (year[-1]=='х' or year[-1]=='x'):
            return int(year[:-1])*10
        elif year[:-6].isdigit() and year[-6:]=='-е гг.':
            return int(year[:-6])

YEAR_MIN = 1794
YEAR_MAX = 2021
COLOR_MIN = (255, 200, 0)
COLOR_MAX = (0, 200, 255)
COLOR_RANGE = (COLOR_MAX[0]-COLOR_MIN[0], COLOR_MAX[1]-COLOR_MIN[1], COLOR_MAX[2]-COLOR_MIN[2])

# TODO ensure that brightness is equal for all building colors
def get_color(year):
    if year is not None:
        k = (year - YEAR_MIN) / YEAR_MAX - YEAR_MIN
        color = (int(COLOR_MIN[0]+(COLOR_MAX[0]-COLOR_MIN[0])*k), int(COLOR_MIN[1]+(COLOR_MAX[1]-COLOR_MIN[1])*k), int(COLOR_MIN[2]+(COLOR_MAX[2]-COLOR_MIN[2])*k))
    else:
        color = (152, 152, 152)
    return '#'+hex(1*2**24+color[0]*2**16+color[1]*2**8+color[2])[3:]

# TODO apply fixtures for individual osm buildings
# now only bindings with non-empty osm building lists are useful to us
print('Merging into PostGIS...')
postgis_con = psycopg2.connect('host='+os.getcwd()+' dbname=mydb')
postgis_cur = postgis_con.cursor()
#postgis_cur.execute('ALTER TABLE planet_osm_polygon ADD COLUMN IF NOT EXISTS color integer')
postgis_cur.execute('ALTER TABLE planet_osm_polygon ADD COLUMN IF NOT EXISTS color char(7)')
for idx, key in enumerate(index_by_osm_building_ids.keys):
    binding = index_by_osm_building_ids.values[idx]
    if binding[2][0] != key: # must have already checked this binding before by its smallest osm building id
        continue
    print(binding)
    # check df building lists and only proceed if all df buildings in list have same years
    df_buildings = list(df_cur.execute('SELECT * FROM buildings WHERE id IN ('+', '.join(['?']*len(binding[0]))+')', binding[0]))
    # TODO
    df_buildings_m = False
    year = None
    for df_building in df_buildings:
        df_building_year = get_year(df_building['construction_end'] if df_building['construction_end'] is not None else df_building['construction_begin'])
        if df_buildings_m and df_building_year != year:
            year = None
            break
        df_buildings_m = True
        year = df_building_year
    if year is None:
        continue # will set default color with single query
    color = get_color(year)
    postgis_cur.execute('UPDATE planet_osm_polygon SET color=%s WHERE osm_id IN ('+', '.join(['%s']*len(binding[2]))+')', [color]+[osm_building_id[1] if osm_building_id[0]=='w' else -osm_building_id[1] for osm_building_id in binding[2]])
postgis_cur.execute('UPDATE planet_osm_polygon SET color=%s WHERE color IS NULL', (get_color(None),))
postgis_con.commit()

exit()

print('Rendering tiles...')
import generate_tiles3
# TODO calculate bbox from content
bbox = (30.6114013, 46.3427070, 30.8313753, 46.6291187)
mapfile = './mapnik.xml'
tile_dir = './tiles/'
generate_tiles3.render_tiles(bbox, mapfile, tile_dir)

# TODO generate binary index of OSM buildings/polygons and building description files
