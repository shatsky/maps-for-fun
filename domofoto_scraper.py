import requests
from bs4 import BeautifulSoup
import sqlite3


def fetch(url):
    print('fetching', url)
    return requests.get(url).content


def parse(text):
    #print(text.decode())
    return BeautifulSoup(text)


def insert(table, item):
    print(table, item)
    try:
        cur.execute('INSERT INTO ' + table + ' (' + ', '.join(item.keys()) + ') VALUES (' + ', '.join([':'+k for k in item.keys()]) + ')', item)
        con.commit()
    except sqlite3.IntegrityError:
        pass


month_names = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря']
def get_photo_date(date_str):
    if date_str.endswith(' (примерно)'):
        date_str = date_str[:-len(' (примерно)')]
    if not date_str.endswith(' г.'):
        return
    date_str, year = date_str[:-1-4-len(' г.')], date_str[-4-len(' г.'):-len(' г.')]
    if not year.isdigit():
        return
    if not date_str == '':
        if ' ' not in date_str:
            return
        day, month_name = date_str.rsplit(' ', 1)
        if not month_name in month_names:
            return
        month = str(month_names.index(month_name)+1)
        if len(month) == 1:
            month = '0' + month
        if not day.isdigit():
            return
        if not len(day) < 3:
            return
        if len(day) == 1:
            day = '0' + day
    else:
        return year
    return year + '-' + month + '-' + day


def first(iterable, condition=lambda x: True):
    try:
        #return next(x for x in iterable if condition(x))
        for item in iterable:
            if condition(item):
                return item
    #except StopIteration:
    #    return
    except TypeError:
        return


con = sqlite3.connect('domofoto.db')
cur = con.cursor()
cur.execute('''CREATE TABLE IF NOT EXISTS buildings
               (id INTEGER PRIMARY KEY, project_id INTEGER, floor_count TEXT, construction_started TEXT, construction_finished TEXT, name_or_purpose TEXT, current_state TEXT, location_lat TEXT, location_lng TEXT, description TEXT, address TEXT)''')
cur.execute('''CREATE TABLE IF NOT EXISTS streets
               (id INTEGER PRIMARY KEY, name TEXT)''')
cur.execute('''CREATE TABLE IF NOT EXISTS addresses
               (building_id INTEGER, street_id INTEGER, number TEXT, PRIMARY KEY (building_id, street_id))''')
cur.execute('''CREATE TABLE IF NOT EXISTS projects
               (id INTEGER PRIMARY KEY, name TEXT)''')
cur.execute('''CREATE TABLE IF NOT EXISTS photos
               (id INTEGER PRIMARY KEY, date TEXT)''')
cur.execute('''CREATE TABLE IF NOT EXISTS building_photos
               (building_id INTEGER, photo_id INTEGER, PRIMARY KEY (building_id, photo_id))''')
st = 0
#st = 180
while True:
    buildings_page = parse(fetch('https://domofoto.ru/list.php?cid=4'+('&st='+str(st) if st>0 else '')))
    # find 1st table which has 'Улица, номер дома' header cell
    page_buildings_found = False
    for buildings_table in buildings_page.select('div.p20w > table'):
        buildings_table_rows = buildings_table.find_all('tr', recursive=False)
        if len(buildings_table_rows) < 2:
            continue
        buildings_table_header = buildings_table_rows[0]
        building_link_col_i = None
        for i, buildings_table_header_cell in enumerate(buildings_table_header.find_all('th', recursive=False)):
            if buildings_table_header_cell.text == 'Улица, номер дома':
                building_link_col_i = i
                break
        if building_link_col_i is None:
            continue
        for buildings_table_row in buildings_table_rows[1:]:
            building = {}
            for buildings_table_row_cell in buildings_table_row.find_all('td', recursive=False)[building_link_col_i:]:
                #print(buildings_table_row_cell)
                for building_link in buildings_table_row_cell.find_all('a', recursive=False):
                    if not (building_link.get('href').startswith('/object/') and building_link.get('href').endswith('/')):
                        continue
                    page_buildings_found = True
                    building['id'] = int(building_link.get('href')[len('/object/'):-len('/')])
                    building_address = building_link.text
                    building['address'] = building_link.text
                    building_page = parse(fetch('https://domofoto.ru/object/'+str(building['id'])+'/'))
                    # find 1st table which has 'Местонахождение:' in 1st cell
                    #for table in building_page.select('td#top-image > table', recursive=False):
                    for table in building_page.find_all('table'):
                        building_info_rows = table.find_all('tr', recursive = False)
                        if len(building_info_rows) < 1:
                            continue
                        building_location_row_cells = building_info_rows[0].find_all('td', recursive = False)
                        if len(building_location_row_cells) < 2:
                            continue
                        if building_location_row_cells[0].text != 'Местонахождение:':
                            continue
                        #street_i = 0
                        # cannot assume that order of buildings in unstructured str (w/ numbers) and structured (w/o numbers) is same
                        for _ in building_location_row_cells[1].find_all('img', recursive=False):
                            streets = []
                            for location_link in _.find_all('a', recursive=False):
                                #print(location_link)
                                if not location_link.get('href', '').startswith('/list.php?uid='):
                                    continue
                                street = {
                                    'id': int(location_link.get('href', '')[len('/list.php?uid='):]),
                                    'name': location_link.text
                                }
                                streets.append(street)
                                insert('streets', street)
                            address_parts = building_address.split(' / ')
                            for street in streets:
                                address = {
                                    'building_id': building['id'],
                                    'street_id': street['id']
                                }
                                for address_part in address_parts:
                                    if address_part == street['name']:
                                        address['number'] = ''
                                    elif address_part.startswith(street['name']+', '):
                                        address['number'] = address_part[len(street['name']+', '):]
                                insert('addresses', address)
                            break
                        for building_info_row in building_info_rows[1:]:
                            building_info_row_cells = building_info_row.find_all('td', recursive = False)
                            if len(building_info_row_cells) < 2:
                                if building_info_row_cells[0].get('colspan') == '2':
                                    building['description'] = building_info_row_cells[0].text
                                continue
                            if building_info_row_cells[0].text == 'Серия:':
                                pass
                            elif building_info_row_cells[0].text == 'Проект:':
                                for project_link in building_info_row_cells[1].find_all('a', recursive = False):
                                    if not (project_link.get('href', '').startswith('/projects/') and project_link.get('href', '').endswith('/')):
                                        continue
                                    project = {
                                        'id': project_link.get('href')[len('/projects/'):-len('/')],
                                        'name': project_link.text
                                    }
                                    insert('projects', project)
                                    building['project_id'] = project['id']
                                    break
                            elif building_info_row_cells[0].text == 'Первоначальный проект:':
                                pass
                            elif building_info_row_cells[0].text == 'Архитекторы:':
                                pass
                            elif building_info_row_cells[0].text == 'Подрядчик:':
                                pass
                            elif building_info_row_cells[0].text == 'Этажность:':
                                building['floor_count'] = building_info_row_cells[1].text
                            elif building_info_row_cells[0].text == 'Начало строительства:':
                                building['construction_started'] = building_info_row_cells[1].text
                            elif building_info_row_cells[0].text == 'Окончание строительства:':
                                building['construction_finished'] = building_info_row_cells[1].text
                            elif building_info_row_cells[0].text == 'Строительство:':
                                construction_start_end = building_info_row_cells[1].text
                                if '—' in construction_start_end:
                                    building['construction_started'], building['construction_finished'] = construction_start_end.split('—', 1)
                                else:
                                    building['construction_started'], building['construction_finished'] = (construction_start_end, construction_start_end)
                            elif building_info_row_cells[0].text == 'Реконструкция:':
                                pass
                            elif building_info_row_cells[0].text == 'Стиль:':
                                pass
                            elif building_info_row_cells[0].text == 'Текущее состояние:':
                                building['current_state'] = building_info_row_cells[1].text
                            elif building_info_row_cells[0].text == 'Название/назначение:':
                                building['name_or_purpose'] = building_info_row_cells[1].text
                        break
                    for script in building_page.find_all('script'):
                        if script.string is not None and '\n	initMap(' in script.string:
                            building['location_lat'], building['location_lng'] = script.string.split('\n	initMap(', 1)[1].split('\n', 1)[0].split(', ', 2)[0:2]
                            break
                    insert('buildings', building)
                    for td_pb_photo in building_page.find_all('td', class_='pb_photo'):
                        photo = {}
                        a_prw = first(td_pb_photo.contents, lambda child: child.name=='a' and 'prw' in child.attrs.get('class',[]))
                        if a_prw is not None:
                            photo['id'] = a_prw.attrs['href'].split('/')[2]
                        else:
                            continue
                        b = first(first(first(td_pb_photo.parent.contents, lambda child: child.name=='td' and 'pb_descr' in child.attrs.get('class', [])), lambda child: child.name=='p' and 'sm' in child.attrs.get('class', [])), lambda child: child.name=='b')
                        if b is not None:
                            photo['date'] = get_photo_date(b.text)
                        insert('photos', photo)
                        insert('building_photos', {'building_id': building['id'], 'photo_id': photo['id']})
                    break
                break
    if not page_buildings_found:
        break
    st += 30
