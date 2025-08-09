# gta2-map-compressor
It compress an uncompressed GMP map file for PC or PSX version of GTA2. 

# How to use

Requires:
- Python 3.x installed and registered on PATH environment

Firstly edit "run_compresser.bat" (using notepad or other text editor) to configure the gmp compressor. Change the following line replacing the last two parameters by you map path and the compression type:

python compress_gmp.py (map path) (PC/PSX)

Examples: if your map is in the same folder of the compressor, you can just type the map name:

- python compress_gmp.py my_map.gmp PC
- python compress_gmp.py my_map.gmp PSX

If you want to include a path to the file, here is an example:

- python compress_gmp.py C:\Users\Desktop\my_map.gmp PC

Running:
Run run_compresser.bat and wait the process finish. The output map compressed will be created on the map's folder.

# Creating a PSX map

First you need the .sty files with all PSX tiles, which can be download here (PSX_sty.zip): https://gtamp.com/forum/viewtopic.php?t=1395

Then create a map in official DMA Map Editor using one of those .sty files (psx_wil.sty if you want to replace Downtown, etc.) and save it. You can start from the original districts (download "PSX_maps.zip" on the link above). Ensure that all tiles on your map have indices between 0 and 383, otherwise unexpected results can happen.

After saving it (you don't need to compress it on the map editor), use this compressor in PSX mode to create a PSX gmp version of your map.

# Installing a PSX map

First you need a program to dump and build PSX ISOs, such as mkpsxiso. After dumping the .iso file, you just need to replace one of the original maps of the game (renaming your map file to one of those below):

- WIL.GMP (Downtown District)
- STE.GMP (Residential District)
- BIL.GMP (Industrial District)

Then rebuild the iso with the changes and it's ready to play.

# Known problems

- Intermediary gradient slopes with side tiles aren't fixed yet, so if you put tiles on an incomplete gradient slope, the forbidden side will be rendered in-game as a weird wall, preventing the player from passing through the slope.
- Hidden surfaces removal is not implemented yet.
