#
# Copyright © 2013-2024 NVIDIA CORPORATION & AFFILIATES. ALL RIGHTS RESERVED.
#
# This software product is a proprietary product of Nvidia Corporation and its affiliates
# (the "Company") and all right, title, and interest in and to the software
# product, including all associated intellectual property rights, are and
# shall remain exclusively with the Company.
#
# This software product is governed by the End User License Agreement
# provided with the software product.
#
import os
from pathlib import Path
import shutil
from typing import List
from loganalyze.logs_extraction.base_extractor import BaseExtractor

class DirectoryExtractor(BaseExtractor):
    def __init__(self, dir_path:Path):
        dir_path = self.is_exists_get_as_path(dir_path)
        if dir_path and dir_path.is_dir():
            self.dir_path = dir_path
        else:
            raise FileNotFoundError(f"Could not use {dir_path}, "
                                    "make sure it exists and is a directory")

    def extract_files(self, files_to_extract: List[str], destination: str):
        if not os.path.exists(destination):
            os.makedirs(destination)

        # Convert the list to a set for faster lookup
        files_to_extract = set(files_to_extract)
        found_files = set()
        not_found_files = set(files_to_extract)

        # Traverse the source directory and its subdirectories
        for root, _, files in os.walk(self.dir_path):
            for file_name in files:
                if file_name in files_to_extract:
                    src_file_path = os.path.join(root, file_name)
                    dest_file_path = os.path.join(destination, file_name)
                    shutil.copy2(src_file_path, dest_file_path)
                    found_files.add(dest_file_path)
                    not_found_files.discard(file_name)

                    # Stop if all files have been found
                    if not not_found_files:
                        return found_files, not_found_files

        return found_files, not_found_files
