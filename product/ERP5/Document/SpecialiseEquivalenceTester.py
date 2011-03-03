# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2010 Nexedi SA and Contributors. All Rights Reserved.
#          Julien Muchembled <jm@nexedi.com>
#
# WARNING: This program as such is intended to be used by professional
# programmers who take the whole responsibility of assessing all potential
# consequences resulting from its eventual inadequacies and bugs
# End users who are looking for a ready-to-use solution with commercial
# guarantees and support are strongly advised to contract a Free Software
# Service Company
#
# This program is Free Software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
##############################################################################

from Products.ERP5.Document.CategoryMembershipEquivalenceTester \
  import CategoryMembershipEquivalenceTester

class SpecialiseEquivalenceTester(CategoryMembershipEquivalenceTester):
  """
  The purpose of this divergence tester is to check the
  consistency between delivery movement and simulation movement
  for a specific category.
  """
  meta_type = 'ERP5 Specialise Equivalence Tester'
  portal_type = 'Specialise Equivalence Tester'

  tested_property = ('specialise',)

  @staticmethod
  def _getTestedPropertyValue(movement, property):
    if movement.getPortalType() == 'Simulation Movement':
      return movement.getSpecialiseList()
    # following line would work for prevision movements, but it is slower
    return [x.getRelativeUrl()
      for x in movement.getInheritedSpecialiseValueList()]
