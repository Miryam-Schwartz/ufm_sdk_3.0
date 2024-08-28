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
# pylint: disable=missing-function-docstring
# pylint: disable=missing-class-docstring
# pylint: disable=missing-module-docstring


class UFMTopAnalyzer:
    def __init__(self):
        self._analyzers = []

    def add_analyzer(self, analyzer):
        self._analyzers.append(analyzer)

    def full_analysis(self):
        """
        Returns a list of all the graphs created and their title
        """
        graphs_and_titles = []
        for analyzer in self._analyzers:
            tmp_images_list = analyzer.full_analysis()
            if len(tmp_images_list) > 0:
                graphs_and_titles.extend(tmp_images_list)
        return graphs_and_titles
