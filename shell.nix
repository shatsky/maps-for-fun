# systemd-run --user --service-type=forking pg_ctl -D $PWD/mydb -l $PWD/logfile -o "--unix_socket_directories='$PWD'" start
# psql --host $PWD mydb
#   CREATE EXTENSION postgis;
#   CREATE EXTENSION hstore;
# osm2pgsql --host $PWD --database mydb --hstore out.osm
# env MAPNIK_MAP_FILE=mapnik.xml MAPNIK_TILE_DIR=./tiles python3 generate_tiles3.py
{ pkgs ? import <nixpkgs> {} }:
  pkgs.mkShell {
    # nativeBuildInputs is usually what you want -- tools you need to run
    #nativeBuildInputs = [ pkgs.postgis pkgs.postgresql ];
    nativeBuildInputs = [ (pkgs.postgresql.withPackages (pkgs: [ pkgs.postgis ])) pkgs.osm2pgsql pkgs.python3Packages.python-mapnik pkgs.python3Packages.psycopg2 pkgs.python3Packages.requests pkgs.python3Packages.beautifulsoup4 ];
}
