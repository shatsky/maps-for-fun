import os
import bisect
import sqlite3
import json

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

    def find_idx(self, key):
        idx = bisect.bisect_left(self.keys, key)
        if idx < len(self.keys):
            if self.keys[idx] == key:
                return idx

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
        k = (year - YEAR_MIN) / (YEAR_MAX - YEAR_MIN)
        color = (int(COLOR_MIN[0]+(COLOR_MAX[0]-COLOR_MIN[0])*k), int(COLOR_MIN[1]+(COLOR_MAX[1]-COLOR_MIN[1])*k), int(COLOR_MIN[2]+(COLOR_MAX[2]-COLOR_MIN[2])*k))
    else:
        color = (152, 152, 152)
    return '#'+hex(1*2**24+color[0]*2**16+color[1]*2**8+color[2])[3:]

valid_df_building_states = [
    '\u00a0Используется\u00a0',
    '\u00a0Строится\u00a0',
    '\u00a0На реконструкции\u00a0',
    '\u00a0Не используется (заброшено)\u00a0'
]

con = sqlite3.connect('domofoto.db')
con.row_factory = dict_factory
cur = con.cursor()
postgis_con = psycopg2.connect('host='+os.getcwd()+' dbname=mydb')
postgis_cur = postgis_con.cursor()
index_by_osm_building_ids = Index()
print('SELECT * FROM buildings WHERE (construction_started IS NOT NULL OR construction_finished IS NOT NULL) AND current_state IN ('+', '.join(['"'+valid_building_state+'"' for valid_building_state in valid_df_building_states])+')')
df_buildings = cur.execute('SELECT * FROM buildings WHERE (construction_started IS NOT NULL OR construction_finished IS NOT NULL) AND current_state IN ('+', '.join(['"'+valid_building_state+'"' for valid_building_state in valid_df_building_states])+')')
for df_building in df_buildings:
    #print(df_building)
    df_building_id = df_building['id']
    postgis_cur.execute('SELECT * FROM planet_osm_polygon WHERE ST_Within(ST_Transform(ST_SetSRID(ST_MakePoint(%s, %s), 4326), 3857), way) AND building IS NOT NULL', (df_building['location_lng'], df_building['location_lat']))
    osm_buildings = list(postgis_cur.fetchall())
    print('osm_buildings_n:'+('0' if len(osm_buildings)==0 else '1' if len(osm_buildings)==1 else 'M')+' df_building_id:'+str(df_building['id'])+' osm_building_ids:'+str([osm_building[0] for osm_building in osm_buildings]))
    # seems that multiple (overlapping) buildings is always mistake, there are very few of them
    if len(osm_buildings)!=1:
        continue
    osm_building = osm_buildings[0]
    osm_building_id = osm_building[0]
    # detecting inconsistencies
    # ensure that there are no other df_buildings located inside this osm_building
    idx = index_by_osm_building_ids.find_idx(osm_building_id)
    if idx is not None:
        index_by_osm_building_ids.values[idx].append(df_building)
    else:
        index_by_osm_building_ids.insert(osm_building_id, [df_building])
postgis_cur.execute('ALTER TABLE planet_osm_polygon ADD COLUMN IF NOT EXISTS color char(7)')
# TODO only iterate osm_buildings which are in index
# TODO we actually need to map all buildings, not only those with years
for osm_building_id in index_by_osm_building_ids.keys:
    # check if it has only df_building in index
    df_buildings = index_by_osm_building_ids.find(osm_building_id)
    if len(df_buildings) == 1:
        df_building = df_buildings[0]
        # set color
        year = get_year(df_building['construction_finished'] if df_building['construction_finished'] is not None else df_building['construction_started'])
        color = get_color(year)
        print('color:'+color+' osm_building_id:'+str(osm_building_id))
        postgis_cur.execute('UPDATE planet_osm_polygon SET color=%s WHERE osm_id=%s', (color, osm_building_id))
    osm_building_file_path = 'tiles/osm_buildings/'+('w' if osm_building_id>0 else 'r')+str(abs(osm_building_id))+'.json'
    with open(osm_building_file_path) as fp:
        osm_building_file_data = json.load(fp)
    osm_building_file_data['df_ids'] = [df_building['id'] for df_building in df_buildings]
    with open(osm_building_file_path, 'w') as fp:
        json.dump(osm_building_file_data, fp)
    df_building_file_path = 'tiles/df_buildings/'+str(df_building['id'])+'.json'
    if not os.path.exists(df_building_file_path):
        df_building_file_data = {}
    else:
        with open(df_building_file_path) as fp:
            df_building_file_data = json.load(fp)
    df_building_file_data.update(**{
        'address': df_building['address'],
        'construction_started': df_building['construction_started'],
        'construction_finished': df_building['construction_finished'],
        'name_or_purpose': df_building['name_or_purpose'],
        'photos': [photo['id'] for photo in reversed(list(cur.execute('SELECT * FROM photos JOIN building_photos ON building_photos.photo_id=photos.id WHERE building_id=? ORDER BY date', (df_building['id'],))))]
    })
    with open(df_building_file_path, 'w') as fp:
        json.dump(df_building_file_data, fp)

postgis_cur.execute('UPDATE planet_osm_polygon SET color=%s WHERE color IS NULL', (get_color(None),))
postgis_con.commit()

# TODO if there are other osm_buildings with same addr and they are not bound to other df_buildings
