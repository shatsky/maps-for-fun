def get_year(year):
    # 1961
    # 04.1961
    # 196x
    # 1960-е гг.
    if isinstance(year, str):
        if year.isdigit():
            return int(year)
        elif year[0:2].isdigit() and year[2]=='.' and year[3:].isdigit():
            return int(year[3:])
        elif year[:-1].isdigit() and (year[-1]=='х' or year[-1]=='x'):
            return int(year[:-1])*10
        elif year[:-6].isdigit() and year[-6:]=='-е гг.':
            return int(year[:-6])

def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

layer = QgsProject.instance().mapLayers()[LAYER_NAME]
features = layer.getFeatures()
import sqlite3
con = sqlite3.connect(DB_PATH)
con.row_factory = dict_factory
cur = con.cursor()
max_ = lambda a, b: max(a, b) if (a is not None and b is not None) else a if a is not None else b
for feature in features:
    rows = cur.execute('SELECT * FROM addresses JOIN buildings ON buildings.id=addresses.building_id JOIN streets ON streets.id=addresses.street_id WHERE streets.name=? AND addresses.number=?', (feature['addr:street'], feature['addr:housenumber']))
    year = None
    for row in rows:
        year = max_(year, max_(get_year(row['construction_begin']), get_year(row['construction_end'])))
    if year is None:
        continue
    feature['year'] = year
    print(feature['year'])
    layer.updateFeature(feature)
