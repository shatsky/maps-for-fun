This document describes the flow of creating a map of buildings colored by construction year. It can be used as a reference to do a similar project, i. e. rendering some OSM features with colors decided from some external data

# Simplified flow
- extract data from OSM
- get external data and merge it using some logic to match external data records to osm features, possibly transform it
- render tiles with rules to pick color for a feature from external data associated with it

# Some technical decisions
- the map itself is in fact a pyramid of 256x256 pre-rendered raster tiles, animated with leaflet.js library (like most interactive web maps are today)
- I started with QGIS and its plugins, but dropped it in favor of using OSM Overpass/.osm file/PostGIS/Mapnik via self-written scripts for numerous reasons including: QGIS losing non-spatial relations (house-to-street) on import; imperfect tile rendering with QGIS plugin; inefficient feature colouring control; desire to automate re-generating everything with updated source data
- to simplify Mapnik rendering rules, I write precalculated colors to PostGIS column and use it as source for value in single mapnik rule (hex ascii string, tried RGBA int but seemingly-correct Mapnik expression for picking component values from it failed for me)
- To avoid need of backend or preloading unnessesary data for displaying clicked building info, I've implemented getting outer border of single-colored area clicked by user and getting building ids within bbox of this area with precalculated kdbush.js index of buildings (index of approximate "visual center of a polygon" points for each building polygon, ~500KiB, loaded only if user clicks on map); for building ids found, <osm_id>.json files are requested, with polygon geometries used to find the building which actually contains the clicked point and display information about it
- kdbush.js is modified to allow arbitrary ids (original uses incremental values, I wanted to index OSM ids to avoid need of separate index_id-to-osm_id index); it's also important to note that kdbush.js from not-yet-merged branch "v4" is used, allowing to store and use already mentioned precalculated index binary file (mainline currently requires generating index by adding points just before using it, I didn't want to waste user device power on this)

# Some OSM notes
- OSM has 3 element types: "node" (point), "way" (continious polyline, possibly enclosed) and "relation" (binding any objects of any of these 3 types, can represent complex geometries or abstract relations); each type has separate id space
- OSM elements have tags; tag has key and value, both are strings
- OSM buildings are represented with OSM elements tagged with "building"=any value, can be empty; valid OSM building is either "way" (enclosed, i. e. simple polygon) or "relation" (of multiple simple polygons, one as "outer" and others as "inner", i. e. polygon with holes)
- OSM has 2 different representations of building address: tags ("street"+"housenumber" tags) and "streetAssociation" relation (relation with tag "type"="streetAssociation")
- .osm xml format is OSM standard "exchange" format which fits any OSM data
- Overpass API is standard way to get small OSM extract like buildings of single city (possibly not useable for world biggest cities)
- Mapnik used to support rendering from .osm file directly, but no longer does; .osm -> PostGIS -> Mapnik is really the easiest way to get it properly rendered now
- PostGIS database created from .osm file via osm2pgsql is not similar to primary OSM database; in fact, it can't even fit all OSM data, non-spatial relations like "streetAssociation" are dropped, therefore osm2pgsql import is called "lossy"; however OSM itself uses it in rendering pipeline, dumping information from "primary" database for consumption by Mapnik
- osm2pgsql stores both "way" and "relation" geometries in single table; since these have separate id spaces, it puts "way" ids as-is and makes "relation" ids negative to avoid collisions

# Detailed flow
1. Extract OSM data
2. [after 1] Load OSM data into PostGIS. It's needed to render with Mapnik.
 `osm2pgsql --host </path/to/postgresql/data/dir/> --database <database_name> --hstore </path/to/file.osm>`
3. [after 2] Merge external information which is used for rendering. I've used domofoto.ru which has construction years and other info for lots of buildings in ex-USSR
 - scrape_domofoto.py (scrapes domofoto.ru into domofoto.db sqlite database)
 - merge_by_location.py (finds matching domofoto records for osm buildings by coords in domofoto data, picks colors based on domofoto data and writes it to column in PostGIS db table, also writes domofoto data to df_buildings/<df_id>.json files and writes df_ids to osm_buildings/<osm_id>.json files, latter used to display information about clicked building)
4. [after 3] Render tiles pyramid
5. [after 1] Generate spatial index of OSM buildings (kdbush.js 2D binary index used in webapp to find buildings that clicked pixel may belong to) and write buildings geometry data to osm_buildings/<osm_id>.json files (used to find exact building, highlight its exact geometry and, with info added to these files in later step, to get extra building info which can be displayed in popup)
 - generate_index.py (produces index_json.js _intermediate_ file and writes buildings geometry data to osm_buildings/<osm_id>.json files, latter used to identify clicked building)
 - generate_index.htm (using index_json.js, produces final binary index and propmts to save it as file; it's somewhat hacky solution to avoid messing with nodejs stack - I decided I don't want to, given that all needed js code can be run in browser)

# Acknowledgments
Thanks to all people who created software and data used in this project, including OSM, Domofoto communities and Vladimir Agafonkin, living god of web cartography (I was truly impressed to find out that 3 important libraries which I found to be most widely used and relevant while solving different subtasks of this project, namely, leaflet.js for displaying the interactive map, polylabel.js for finding "visual center of a polygon" points and kdbush.js for indexing points for quick spatial search, were all created by him)
