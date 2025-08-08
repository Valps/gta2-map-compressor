from pathlib import Path
import shutil
import argparse
import sys
import os

import time

PROGRAM_NAME = os.path.basename(sys.argv[0])
ROOT_DIR = Path(__file__).parent

PLATFORMS = ["pc", "psx"]

MAP_WIDTH = 255
MAP_HEIGHT = 255

MAP_MAX_Z = 7

BLOCK_INFO_SIZE = 12
LIGHT_INFO_SIZE = 16
ZONE_TYPE_COORDS_DATA_SIZE = 5     # not includes the name length neither the name itself

LIGHT_MAX_X = 32767     # 255*128 + 64 - 1, where 64 = max offset
LIGHT_MAX_Y = 32767     # 255*128 + 64 - 1

AIR_TYPE = 0
ROAD_TYPE = 1
PAVEMENT_TYPE = 2
FIELD_TYPE = 3

DMAP_COLUMN_OFFSET = 256*256*4
CMAP_COLUMN_OFFSET = 256*256*2

EMPTY_BLOCK_DATA = bytes( [ 0 for _ in range(BLOCK_INFO_SIZE) ] )

EMPTY_BLOCK_HASH = hash(EMPTY_BLOCK_DATA)

WORD_SIZE = 2
DWORD_SIZE = 4

DATA_SIZE = DWORD_SIZE      # use it for DMAP or CMAP

class DMAP_compressed:
    def __init__(self, data: bytes, num_dwords: int, columns_data: bytes, num_blocks: int, block_info: bytes):
        self.data = data
        self.num_dwords = num_dwords
        self.columns_data = columns_data
        self.num_blocks = num_blocks
        self.block_info = block_info

def get_filename(path):
    str_path = str(path)
    i = str_path.rfind('\\') + 1
    j = str_path.rfind('.')
    return str_path[i:j]

def convert_int_to_dword(integer):  # low endian
    b1 = integer % 256
    b2 = (integer >> 8) % 256
    b3 = (integer >> 16) % 256
    b4 = (integer >> 24) % 256
    return bytes([b1, b2, b3, b4])

def convert_int_to_word(integer):  # low endian
    b1 = integer % 256
    b2 = integer // 256
    return bytes([b1, b2])

#def concatenate_bytes(byte1, byte2):
#    return byte1 + byte2

def read_block_side_info(side, str_side):
    tile_texture_idx = (side % 1024)
    side = side >> 10

    wall = (side % 2)
    side = side >> 1

    bullet_wall = (side % 2)
    side = side >> 1

    flat = (side % 2)
    side = side >> 1

    flip = (side % 2)
    side = side >> 1

    tile_rotation = side

    print(f"{str_side} tile: {tile_texture_idx}")
    #print(f"Tile rotation: {return_rotation_value_str(tile_rotation)}°")
    #print(f"Wall: {wall}, Bullet Wall: {bullet_wall}")
    #print(f"Flat: {flat}")
    #print(f"Flip: {flip}")

def read_lid_info(lid):
    tile_texture_idx = (lid % 1024)
    lid = lid >> 10

    lighting_filter = (lid % 4)
    lid = lid >> 2

    flat = (lid % 2)
    lid = lid >> 1

    flip = (lid % 2)
    lid = lid >> 1

    tile_rotation = lid

    print(f"Lid tile: {tile_texture_idx}")
    #print(f"Tile rotation: {tile_rotation}°")
    #print(f"Filter: {lighting_filter}")
    #print(f"Flat: {flat}")
    #print(f"Flip: {flip}")

def is_slope(block_data):
    slope_byte = block_data[-1]
    slope_byte = slope_byte >> 2
    if (slope_byte == 0):
        return False
    if (slope_byte > 60):
        return False
    return True

def print_all_info_block_data(block_data):
    left_side = int.from_bytes(block_data[0:2], 'little')
    right_side = int.from_bytes(block_data[2:4], 'little')
    top_side = int.from_bytes(block_data[4:6], 'little')
    bottom_side = int.from_bytes(block_data[6:8], 'little')
    lid = int.from_bytes(block_data[8:10], 'little')

    #print("Left side info:")
    read_block_side_info(left_side, "Left")

    #print("\nRight side info:")
    read_block_side_info(right_side, "Right")

    #print("\nTop side info:")
    read_block_side_info(top_side, "Top")

    #print("\nBottom side info:")
    read_block_side_info(bottom_side, "Bottom")

    #print("\nLid info:")
    read_lid_info(lid)

def fix_psx_slope(block_data):
    slope_byte = block_data[-1]
    slope_byte = slope_byte >> 2
    if (49 <= slope_byte <= 52):
        lid = int.from_bytes(block_data[8:10], 'little')
        tile_texture_idx = (lid % 1024)
        if tile_texture_idx == 384:
            tile_texture_idx = 1023
            lid = lid | tile_texture_idx    # set all lowest 10 bits to 1  (1111 1111 11 = 1023)
            new_block_data = block_data[:8] + bytes([lid % 256, lid // 256]) + block_data[10:]
        else:
            new_block_data = block_data
    else:
        new_block_data = block_data
    return new_block_data

def detect_headers_and_get_chunks(gmp_path):

    chunk_info = dict(UMAP = [None, None], 
                   CMAP = [None, None], 
                   DMAP = [None, None], 
                   ZONE = [None, None], 
                   MOBJ = [None, None], 
                   PSXM = [None, None], 
                   ANIM = [None, None],
                   LGHT = [None, None],
                   EDIT = [None, None],
                   THSR = [None, None],
                   RGEN = [None, None])
    
    data_array = []

    with open(gmp_path, 'rb') as file:
        
        signature = file.read(4).decode('ascii')
        if (signature != "GBMP"):
            print("Error!\n")
            print(f"{gmp_path} is not a gmp file!")
            sys.exit(-1)

        version_code = int.from_bytes(file.read(2),'little')

        print(f"File Header: {signature}")
        print(f"Version Code: {version_code}", end="\n\n")

        data_offset = file.tell()
        size = file.seek(0, os.SEEK_END)
        file.seek(data_offset)

        print("File Size: {:,} bytes".format(size))

        current_offset = data_offset

        while (current_offset < size):
            #print(f"Current offset: {file.tell()}")
            chunk_header = file.read(4).decode('ascii')
            current_offset += 4
            if (chunk_header == "UMAP" 
                or chunk_header == "CMAP"
                or chunk_header == "DMAP"
                or chunk_header == "ZONE"
                or chunk_header == "MOBJ"
                or chunk_header == "PSXM"
                or chunk_header == "ANIM"
                or chunk_header == "LGHT"
                or chunk_header == "EDIT"
                or chunk_header == "THSR"
                or chunk_header == "RGEN"
                ):
                header_data_offset = file.tell() + 4
                chunk_info[chunk_header][0] = header_data_offset

                header_size = int.from_bytes(file.read(4),'little')
                chunk_info[chunk_header][1] = header_size

                print(f"Header {chunk_header} found! Offset: {hex(header_data_offset)}, Size: {hex(header_size)}")

                data = file.read(header_size)  # read data # skip data
                data_array.append((chunk_header, data))
                
                current_offset += header_size
    print("")
    return chunk_info, data_array

def write_uncompressed_map(output_path, chunk_infos, block_info_array):
    with open(output_path, 'r+b') as file:
        
        umap_offset = chunk_infos["UMAP"][0]
        size = chunk_infos["UMAP"][1]

        file.seek(umap_offset)
        
        current_offset = umap_offset

        x = 0
        y = 0
        z = 0

        while (current_offset < umap_offset + size):
            file.write(block_info_array[z][y][x])

            x += 1

            if (x > 255):
                x = 0
                y += 1
                
            if (y > 255):
                y = 0
                z += 1
                
            if (z >= 8):
                break

############ DMAP stuff

def DMAP_read_all_columns(gmp_path, chunk_infos):
    
    with open(gmp_path, 'rb') as file:
        
        dmap_offset = chunk_infos["DMAP"][0]
        size = chunk_infos["DMAP"][1]

        file.seek(dmap_offset + DMAP_COLUMN_OFFSET)
        column_words = int.from_bytes(file.read(4), 'little')

        print(f"Num of columns words: {column_words}")

        words = 0
        column_idx = 0

        while (words < 2*column_words):
            start_offset = file.tell()

            column_height = int.from_bytes(file.read(1))
            column_offset = int.from_bytes(file.read(1))
            num_blocks = column_height - column_offset
            
            if column_height > 7:
                print(f"\nError: height {column_height} above 7. Column {column_idx} at offset {hex(start_offset)}")
                print(f"words count = {words}")
                sys.exit(-1)

            if column_offset > 7:
                print(f"\nError: BlockOffset {column_offset} above 7. Column {column_idx} at offset {hex(start_offset)}")
                print(f"words count = {words}")
                sys.exit(-1)

            # get back to start position
            file.seek(start_offset)

            # 1 for height, 1 for offset, 2 for pad, 4*num_blocks for blockd
            column_size = 1 + 1 + 2 + 4*num_blocks

            if column_size < 0:
                print(f"ERROR: negative column_size: {column_size}")
                print(f"Column: {column_idx}, Height = {column_height}, Block Offset = {column_offset}")
                print(f"File Offset: {hex(start_offset)}")
                sys.exit(-1)

            file.read(column_size)

            words += column_size // 2
            column_idx += 1
        
        print(f"Number of columns: {column_idx}")

        column_finish_offset = file.tell()

        print(f"Column data finish offset: {hex(column_finish_offset)}")

        num_total_blocks = int.from_bytes(file.read(4), 'little')
        print(f"Num of unique blocks: {num_total_blocks}")

    return column_finish_offset + 4

def DMAP_decompress(gmp_path, chunk_infos, column_finish_offset):
    # initialize block info array with empty blocks
    empty_block_data = bytes([0 for _ in range(BLOCK_INFO_SIZE)])
    block_info_array = [ [ [empty_block_data for _ in range(MAP_WIDTH+1)] for _ in range(MAP_HEIGHT+1) ] for _ in range(MAP_MAX_Z+1) ]

    with open(gmp_path, 'rb') as file:
        
        dmap_offset = chunk_infos["DMAP"][0]
        size = chunk_infos["DMAP"][1]

        for y in range(MAP_HEIGHT+1):
            for x in range(MAP_WIDTH+1):
                tgt_block_column_data_offset = dmap_offset + 4*(x + y*256)

                file.seek(tgt_block_column_data_offset)

                words_offset = int.from_bytes(file.read(4), 'little')
                tgt_column_offset = dmap_offset + DMAP_COLUMN_OFFSET + 4 + 4*words_offset

                file.seek(tgt_column_offset)

                column_height = int.from_bytes(file.read(1))
                column_offset = int.from_bytes(file.read(1))
                num_blocks = column_height - column_offset

                #print(f"x,y = ({x}, {y})")
                #print(f"Height: {column_height}")
                #print(f"Offset: {column_offset}\n\n")

                all_column_blocks_id = []

                file.read(2)    # skip padding
                
                # get all block ids from this column
                for block_idx in range(num_blocks):
                    block_id = int.from_bytes( file.read(4) ,'little' )
                    all_column_blocks_id.append( block_id )

                # block info data starts at
                block_info_array_offset = column_finish_offset

                # get block info from each block using its id
                for blockd_idx, block_id in enumerate(all_column_blocks_id):
                    block_info_offset = block_info_array_offset + block_id*BLOCK_INFO_SIZE
                    file.seek( block_info_offset )
                    block_data = file.read(BLOCK_INFO_SIZE)
                    block_z = column_offset + blockd_idx
                    block_info_array[block_z][y][x] = block_data

    return block_info_array

############ CMAP stuff

def CMAP_read_all_columns(gmp_path, chunk_infos):
    
    with open(gmp_path, 'rb') as file:
        
        dmap_offset = chunk_infos["CMAP"][0]
        size = chunk_infos["CMAP"][1]

        file.seek(dmap_offset + CMAP_COLUMN_OFFSET)
        column_words = int.from_bytes(file.read(2), 'little')

        print(f"Num of columns words: {column_words}")

        words = 0
        column_idx = 0

        while (words < column_words):
            start_offset = file.tell()

            column_height = int.from_bytes(file.read(1))
            column_offset = int.from_bytes(file.read(1))
            num_blocks = column_height - column_offset
            
            if column_height > 7:
                print(f"\nError: height {column_height} above 7. Column {column_idx} at offset {hex(start_offset)}")
                print(f"words count = {words}")
                sys.exit(-1)

            if column_offset > 7:
                print(f"\nError: BlockOffset {column_offset} above 7. Column {column_idx} at offset {hex(start_offset)}")
                print(f"words count = {words}")
                sys.exit(-1)

            # get back to start position
            file.seek(start_offset)

            # 1 for height, 1 for offset, 2*num_blocks for blockd
            column_size = 1 + 1 + 2*num_blocks

            if column_size < 0:
                print(f"ERROR: negative column_size: {column_size}")
                print(f"Column: {column_idx}, Height = {column_height}, Block Offset = {column_offset}")
                print(f"File Offset: {hex(start_offset)}")
                sys.exit(-1)

            file.read(column_size)

            words += column_size // 2
            column_idx += 1
        
        print(f"Number of columns: {column_idx}")

        column_finish_offset = file.tell()
        print(f"Column data start offset: {hex(dmap_offset + CMAP_COLUMN_OFFSET + 2)}")
        print(f"Column data finish offset: {hex(column_finish_offset)}")

        block_data_info_offset = column_finish_offset + 1024 # TODO: psx vs pc CMAP: include 1024 (padding?)
        

        file.seek(block_data_info_offset)  
        num_total_blocks = int.from_bytes(file.read(2), 'little')
        print(f"Num unique blocks: {num_total_blocks}")

        block_data_finish_offset = block_data_info_offset + num_total_blocks*BLOCK_INFO_SIZE


    print(f"Block info start offset = {hex(block_data_info_offset)}")
    print(f"Block info end offset = {hex(block_data_finish_offset)}")

    return block_data_info_offset + 2, block_data_finish_offset, num_total_blocks

def CMAP_decompress(gmp_path, chunk_infos, block_data_finish_offset, block_data_info_offset, num_total_blocks):
    strange_blocks = 0
    normal_blocks = 0
    max_idx_below_8000 = 0
    max_idx_above_8000 = 0
    min_idx_above_8000 = 40000
    # initialize block info array with empty blocks
    empty_block_data = bytes([0 for _ in range(BLOCK_INFO_SIZE)])
    block_info_array = [ [ [empty_block_data for _ in range(MAP_WIDTH+1)] for _ in range(MAP_HEIGHT+1) ] for _ in range(MAP_MAX_Z+1) ]

    with open(gmp_path, 'rb') as file:
        
        cmap_offset = chunk_infos["CMAP"][0]
        size = chunk_infos["CMAP"][1]

        # block info data starts at
        block_info_array_offset = block_data_info_offset

        #print(f"Unknown data again: {hex(block_data_finish_offset + 1536 + 4)}")

        for y in range(MAP_HEIGHT+1):
            for x in range(MAP_WIDTH+1):
                tgt_block_column_data_offset = cmap_offset + 2*(x + y*256)

                file.seek(tgt_block_column_data_offset)

                words_offset = int.from_bytes(file.read(2), 'little')
                tgt_column_offset = cmap_offset + CMAP_COLUMN_OFFSET + 2 + 2*words_offset

                file.seek(tgt_column_offset)

                column_height = int.from_bytes(file.read(1))
                column_offset = int.from_bytes(file.read(1))
                num_blocks = column_height - column_offset

                #if x == 20 and y == 75:
                #    print(f"({x}, {y}) Column offset: {hex(tgt_column_offset)}")

                all_column_blocks_id = []

                # get all block ids from this column
                for block_idx in range(num_blocks):
                    block_id = int.from_bytes( file.read(2), 'little' )

                    # TODO: testing
                    if block_id >= 32768:
                        strange_blocks += 1
                        if block_id > max_idx_above_8000:
                            max_idx_above_8000 = block_id
                        if block_id < min_idx_above_8000:
                            min_idx_above_8000 = block_id
                    else:
                        normal_blocks += 1
                        if block_id > max_idx_below_8000:
                            max_idx_below_8000 = block_id

                    all_column_blocks_id.append( block_id )

                # get block info from each block using its id
                for blockd_idx, block_id in enumerate(all_column_blocks_id):
                    if (block_id < 32768):
                        block_info_offset = block_info_array_offset + BLOCK_INFO_SIZE*block_id  #block_id*BLOCK_INFO_SIZE
                        file.seek( block_info_offset )
                        block_data = file.read(BLOCK_INFO_SIZE)

                        # now fix tile 384 to 1023 for 3-sided slopes
                        if is_slope(block_data):
                            block_data = fix_psx_slope(block_data)
                    else:
                        block_info_offset = block_data_finish_offset + 1536 + 4 + 4*(block_id - 32768)    # 1536 = 0x600
                        file.seek( block_info_offset )
                        lid_slope_data = file.read(4)
                        block_data = bytes([0,0  ,  0,0  ,  0,0  ,  0,0 ]) + lid_slope_data
                    
                    z = column_offset + blockd_idx
                    block_info_array[z][y][x] = block_data

    print(f"Normal blocks with index below 0x8000: {normal_blocks}")
    print(f"Strange blocks with index above 0x8000: {strange_blocks}")
    print(f"Max idx below 0x8000: {max_idx_below_8000}")
    print(f"Max idx above 0x8000: {max_idx_above_8000}; Min idx: {min_idx_above_8000}")
    print(f"Thus, unique blocks with idx above 0x8000: {max_idx_above_8000 - min_idx_above_8000 + 1}")
    return block_info_array




def uncompress_gmp(gmp_path, chunk_infos, psx):

    if not psx and chunk_infos["DMAP"][0] is None:
        print("Error: This program only read compressed maps.")
        sys.exit(-1)

    if psx and chunk_infos["CMAP"][0] is None:
        print("Error: This program only read compressed maps.")
        sys.exit(-1)

    if not psx:
        column_finish_offset = DMAP_read_all_columns(gmp_path, chunk_infos)
        print(f"Column finish offset = {hex(column_finish_offset)}")
        block_info_array = DMAP_decompress(gmp_path, chunk_infos, column_finish_offset)
    else:
        block_data_info_offset, block_data_finish_offset, num_total_blocks = CMAP_read_all_columns(gmp_path, chunk_infos)
        print(f"Unknown data at {hex(block_data_finish_offset + 1536 + 2)}\n")
        block_info_array = CMAP_decompress(gmp_path, chunk_infos, block_data_finish_offset, block_data_info_offset, num_total_blocks)

    return block_info_array

def get_block_info_data_from_UMAP(gmp_path, chunk_infos):

    xyz_array = []

    with open(gmp_path, 'rb') as file:
        umap_offset = chunk_infos["UMAP"][0]
        size = chunk_infos["UMAP"][1]
        file.seek(umap_offset)
        current_offset = umap_offset

        x_array = []
        xy_array = []

        x = 0
        y = 0
        z = 0

        while (current_offset < umap_offset + size):

            block_data = file.read(BLOCK_INFO_SIZE)
            x_array.append(block_data)

            current_offset += BLOCK_INFO_SIZE

            x += 1

            if (x > 255):
                x = 0

                xy_array.append(x_array)
                x_array = []

                y += 1
            
            if (y > 255):
                y = 0

                xyz_array.append(xy_array)
                xy_array = []

                z += 1

    return xyz_array

# not used
def get_block_data_set_from_UMAP(gmp_path, chunk_infos):

    block_set = set()

    with open(gmp_path, 'rb') as file:
        umap_offset = chunk_infos["UMAP"][0]
        size = chunk_infos["UMAP"][1]
        file.seek(umap_offset)
        current_offset = umap_offset

        while (current_offset < umap_offset + size):

            block_data = file.read(BLOCK_INFO_SIZE)
            current_offset += BLOCK_INFO_SIZE
            block_set.add(block_data)

    return block_set

def create_set_from_array(block_info_array):
    block_set = { block_info_array[0][0][0] }
    for z in range(len(block_info_array)):
        for y in range(len(block_info_array[z])):
            for x in range(len(block_info_array[z][y])):
                block_set.add(block_info_array[z][y][x])
    return block_set

def create_columns(block_info_array, block_list):
    columns_array = []
    columns_set = set()

    dword_column_offset = 0
    dword_columns_offset_array = []

    percentage = 0

    init_time = time.time()
    old_time = init_time

    dmap_data_indices = [ [ 0 for _ in range(256) ] for _ in range(256) ]   # init
    dmap_index = 0      # first column

    for y in range(MAP_HEIGHT+1):
        for x in range(MAP_WIDTH+1):
            
            offset = 0
            height = 0
            empty_blocks_finished = False

            blockd_array = []

            #column_block_array = []        # TODO: is this necessary?

            for z in range(MAP_MAX_Z+1):
                block_data = block_info_array[z][y][x]
                if block_data == EMPTY_BLOCK_DATA:
                    if not empty_blocks_finished:
                        offset += 1
                    else:
                        blockd_array.append( 0 ) # block_list.index(block_data)     empty blocks always zero
                else:
                    empty_blocks_finished = True
                    height = z

                    blockd_array.append( block_list.index(block_data) ) # TODO: construct block_list in this function, so this line will run faster

            if offset == MAP_MAX_Z:
                height = 0
                offset = 0

            # encode column height, offset & padding
            column_data = bytes([height, offset, 0, 0])

            num_blocks = height - offset

            # encode blockd
            for block_col_idx in range(num_blocks):     # ignore the highests empty blocks
                column_data += convert_int_to_dword( blockd_array[block_col_idx] )
            


            try:
                # If not raise exception, there is already the column on the array
                dmap_data_indices[y][x] = columns_array.index(column_data)
            except ValueError:
                # new column, so register it
                columns_set.add(column_data)
                columns_array.append(column_data)

                dword_columns_offset_array.append(dword_column_offset)
                dword_column_offset += len(column_data) // DATA_SIZE    # 4 = size of dword

                # encode column dword to populate "data[256][256]"
                dmap_data_indices[y][x] = dmap_index
                dmap_index += 1



            if False:   # old
                if column_data not in columns_set:
                    # new column, so register it
                    columns_set.add(column_data)
                    columns_array.append(column_data)

                    dword_columns_offset_array.append(dword_column_offset)
                    dword_column_offset += len(column_data) // DATA_SIZE    # 4 = size of dword

                    # encode column dword to populate "data[256][256]"
                    dmap_data_indices[y][x] = dmap_index
                    dmap_index += 1
                else:
                    # there is already the column on the array
                    dmap_data_indices[y][x] = columns_array.index(column_data)

            percentage += 0.00001525878

            

            curr_time = time.time()
            if (curr_time - old_time > 5):
                old_time = curr_time
                print("{:.0%}".format(percentage))
                
    print(f"Created columns in {(curr_time - init_time):.3f} seconds")

    return (dmap_data_indices, columns_array, dword_columns_offset_array)


def search_data(input_data, header_to_found):
    for header, data in input_data:
        if header == header_to_found:
            return data
    raise "Header not found"

def create_dmap(dmap_base_indices, columns_array, block_list, dword_columns_offset_array) -> dict:

    dmap_dict = dict(size=0, base=None, column_dwords=0, column_data=None, num_blocks=0, block_info=None)

    # create base data chunk
    base = bytes()
    for y in range(MAP_HEIGHT+1):
        for x in range(MAP_WIDTH+1):
            base += convert_int_to_dword(dmap_base_indices[y][x])

    assert len(base) == DWORD_SIZE*256*256
    dmap_dict["base"] = base

    # create column data
    column_data = bytes()
    column_dwords = dword_columns_offset_array[-1] + ((len(columns_array[-1])) // 4)    #column_dwords = dword_columns_offset_array[-1]
    dmap_dict["column_dwords"] = column_dwords
    for column in columns_array:
        column_data += column
    
    assert len(column_data) == DWORD_SIZE*column_dwords# + len(columns_array[-1])
    dmap_dict["column_data"] = column_data
    
    # create block info data
    block_info = bytes()
    num_blocks = len(block_list)
    dmap_dict["num_blocks"] = num_blocks
    for block_data in block_list:
        block_info += block_data

    assert len(block_info) == BLOCK_INFO_SIZE*num_blocks
    dmap_dict["block_info"] = block_info

    dmap_dict["size"] = len(base) + 4 + len(column_data) + 4 + len(block_info)
    #print("Len base:", hex(len(base)))
    #print("DMAP size:", hex(dmap_dict["size"]))

    return dmap_dict


def create_gmp(output_path, dmap_info, chunk_info, data):  # zones_info_array, all_anim_data, edit_data
    with open(output_path, 'w+b') as file:
        signature = str.encode("GBMP")
        file.write(signature)

        version = convert_int_to_word(500)
        file.write(version)

        # UMAP
        #chunk_header = str.encode("UMAP")
        #file.write(chunk_header)

        #umap_size = convert_int_to_dword(UMAP_SIZE)
        #file.write(umap_size)

        #for z in range(len(block_info_array)):
        #    for y in range(len(block_info_array[z])):
        #        for x in range(len(block_info_array[z][y])):
        #            file.write(block_info_array[z][y][x])

        # DMAP
        chunk_header = str.encode("DMAP")
        file.write(chunk_header)

        dmap_size = convert_int_to_dword(dmap_info["size"])
        file.write(dmap_size)

        file.write(dmap_info["base"])
        file.write(convert_int_to_dword(dmap_info["column_dwords"]))
        file.write(dmap_info["column_data"])
        file.write(convert_int_to_dword(dmap_info["num_blocks"]))
        file.write(dmap_info["block_info"])
        

        # ZONE
        if chunk_info["ZONE"][0] is not None:
            chunk_header = str.encode("ZONE")
            file.write(chunk_header)

            zone_size = convert_int_to_dword(chunk_info["ZONE"][1])
            file.write(zone_size)
            file.write( search_data(data, "ZONE") )

        # PSXM
        if chunk_info["PSXM"][0] is not None:
            chunk_header = str.encode("PSXM")
            file.write(chunk_header)

            psxm_size = convert_int_to_dword(chunk_info["PSXM"][1])
            file.write(psxm_size)
            file.write( search_data(data, "PSXM") )

        # ANIM
        if chunk_info["ANIM"][0] is not None:
            chunk_header = str.encode("ANIM")
            file.write(chunk_header)

            anim_size = convert_int_to_dword(chunk_info["ANIM"][1])
            file.write(anim_size)
            file.write( search_data(data, "ANIM") )

        # LGHT
        if chunk_info["LGHT"][0] is not None:
            chunk_header = str.encode("LGHT")
            file.write(chunk_header)

            lght_size = convert_int_to_dword(chunk_info["LGHT"][1])
            file.write(lght_size)
            file.write( search_data(data, "LGHT") )
        
        # EDIT
        if chunk_info["EDIT"][0] is not None:
            chunk_header = str.encode("EDIT")
            file.write(chunk_header)

            edit_size = convert_int_to_dword(chunk_info["EDIT"][1])
            file.write(edit_size)
            file.write( search_data(data, "EDIT") )

        # RGEN
        if chunk_info["RGEN"][0] is not None:
            chunk_header = str.encode("RGEN")
            file.write(chunk_header)

            rgen_size = convert_int_to_dword(chunk_info["RGEN"][1])
            file.write(rgen_size)
            file.write( search_data(data, "RGEN") )
    return


def main():
    parser = argparse.ArgumentParser(PROGRAM_NAME)
    parser.add_argument("gmp_path")
    #parser.add_argument("platform")
    args = parser.parse_args()

    if (not args.gmp_path):
        #or args.platform.lower() not in PLATFORMS):
        print("Usage: python [program path] [gmp path] [platform=pc,psx]")
        sys.exit(-1)

    # get input gmp path
    if ("\\" not in args.gmp_path and "/" not in args.gmp_path):
        gmp_path = ROOT_DIR / args.gmp_path
    else:
        gmp_path = Path(args.gmp_path)

    # verify if the input gmp map exists
    if (not gmp_path.exists()):
        print(f"Input gmp file doesn't exists. Input Path: {gmp_path}")
        sys.exit(-1)

    #if args.platform.lower() == "psx":
    #    is_psx = True
    #else:
    #    is_psx = False
    
    print(f"\nOpening file {gmp_path}...\n")
    chunk_infos, data = detect_headers_and_get_chunks(gmp_path)

    if chunk_infos["UMAP"][0] is None:
        print("ERROR: There is nothing to compress. UMAP header is missing.")
        sys.exit(-1)

    print("Getting block info from uncompressed data...")
    block_info_array = get_block_info_data_from_UMAP(gmp_path, chunk_infos)
    print("Creating set from block array...")
    block_set = create_set_from_array(block_info_array)     # exclude repeated blocks

    block_list = list(block_set)

    print(f"Num of unique blocks: {len(block_list)}")

    print("Creating columns...")
    dmap_data_indices, columns_array, dword_columns_offset_array = create_columns(block_info_array, block_list)

    #num_dwords = dword_columns_offset_array[-1] #+ (len(columns_array[-1]))//4
    num_dwords = dword_columns_offset_array[-1] + ((len(columns_array[-1])) // 4)

    print(f"Num of dwords: {num_dwords}")
    print(f"Num of columns: {len(columns_array)}")

    dmap_info = create_dmap(dmap_data_indices, columns_array, block_list, dword_columns_offset_array)

    # now materialize the map file
    parent = gmp_path.parent
    map_name = get_filename(gmp_path)
    output_path = parent / (map_name + "_compressed.gmp")
    create_gmp(output_path, dmap_info, chunk_infos, data)

    print("Success!")
    return


















    #block_set = get_block_data_set_from_UMAP(gmp_path, chunk_infos)
    #column_set

    # creating a copy of the target gmp

    filename = get_filename(gmp_path)
    output_path = ROOT_DIR / f"{filename}_compressed.gmp"

    print(f"Creating copy of {filename}.gmp")
    shutil.copyfile(gmp_path, output_path)

    # now inject the block info into output
    print("Injecting block info...")
    write_uncompressed_map(output_path, chunk_infos, block_info_array)

    #print("Copying other gmp chunks...")
    #chunk_dict = get_other_chunks(gmp_path, chunk_infos)

    print("Success!")
        


if __name__ == "__main__":
    main()

