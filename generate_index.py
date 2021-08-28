import xml.etree.ElementTree as ET
import bisect
import sqlite3
import os
import struct
import json

import psycopg2

from polylabel import polylabel


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
building_ids = []
for element in root:
    if 'id' not in element.attrib:
        continue
    if element.tag == 'node' or element.tag == 'way':
        index_by_id.insert((element.tag[0], int(element.attrib['id'])), element)
    for element_child in element:
        if element_child.tag == 'tag':
            tag = element_child
            if tag.attrib['k'] == 'building':
                if element.tag == 'relation':
                    index_by_id.insert(('r', int(element.attrib['id'])), element)
                building_ids.append((element.tag[0], int(element.attrib['id'])))

#index_buildings_by_lonlat = Index()
buildings = []
for building_id in building_ids:
    polygon = [[]]
    building = index_by_id.find(building_id)
    if building_id[0] == 'w':
        for child in building:
            if child.tag == 'nd':
                node = index_by_id.find(('n', int(child.attrib['ref'])))
                polygon[0].append((float(node.attrib['lat']), float(node.attrib['lon'])))
        #print(polygon)
        #result = polylabel(polygon, 0.00001)
        #print(result)
        #index_buildings_by_loglat.insert((result[0][0], result[0][1]), building_id)
        buildings.append([building_id[1] if building_id[0]=='w' else -building_id[1], polygon])
    else:
        inner = []
        for child in building:
            if child.tag == 'member' and child.attrib['type'] == 'way' and child.attrib['role'] in ['outer', 'inner']:
                way = index_by_id.find(('w', int(child.attrib['ref'])))
                way_points = []
                if child.attrib['role'] == 'outer':
                    target = polygon[0]
                elif child.attrib['role'] == 'inner':
                    target = []
                    polygon.append(target)
                for child in way:
                    if child.tag == 'nd':
                        node = index_by_id.find(('n', int(child.attrib['ref'])))
                        target.append((float(node.attrib['lat']), float(node.attrib['lon'])))
    osm_building_file_path = 'tiles/osm_buildings/'+building_id[0]+str(building_id[1])+'.json'
    if not os.path.exists(osm_building_file_path):
        building_file_data = {}
    else:
        with open(osm_building_file_path) as fp:
            building_file_data = json.load(fp)
    building_file_data['polygon'] = polygon
    with open(osm_building_file_path, 'w') as fp:
        json.dump(building_file_data, fp)



#data = b''
#for idx in range(len(index_buildings_by_loglat.keys)):
#    key = index_buildings_by_loglat.keys[idx]
#    value = index_buildings_by_loglat.values[idx]
#    data += struct.pack('ffi', key[0], key[1], value[1] if value[0]=='w' else -value[1])
#
#with open('buildings-index.bin', 'wb') as f: f.write(data)

print(len(buildings))
exit()

import json
with open('buildings_json.js', 'w') as fp:
    fp.write('buildings = ')
    json.dump(buildings, fp)
    fp.write(';')
