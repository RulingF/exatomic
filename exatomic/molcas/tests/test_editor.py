# -*- coding: utf-8 -*-
# Copyright (c) 2015-2017, Exa Analytics Development Team
# Distributed under the terms of the Apache License 2.0
import warnings
from unittest import TestCase
from exatomic.molcas.editor import Editor


class TestEditor(TestCase):
    """Tests that metadata is set appropriately for Molcas editors."""

    def test_no_meta(self):
        """Test that program metadata is set by default."""
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            fl = Editor('')
        self.assertTrue(fl.meta['program'] == 'molcas')

    def test_with_meta(self):
        """Test that passed metadata is respected and program is set."""
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            fl = Editor('', meta={'meta': 'data'})
        self.assertEqual(fl.meta['meta'], 'data')
        self.assertEqual(fl.meta['program'], 'molcas')
