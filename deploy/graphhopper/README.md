# GraphHopper Runtime Files

This folder is the expected mount point for the GraphHopper container in `compose.yaml`.

Place these files here before starting the stack:

- `graphhopper-web-10.2.jar`
- `config-example.yml`
- `foot.json` if your config uses it

The compose service expects:

- jar path: `/srv/graphhopper/graphhopper-web-10.2.jar`
- config path: `/srv/graphhopper/config-example.yml`

The OSM input file is mounted separately from:

- `otp/graphs/default/ireland-and-northern-ireland-260318.osm.pbf`

If you already have a working local GraphHopper setup, copy those working files here as-is. This avoids re-debugging the walking stack during AWS deployment.
