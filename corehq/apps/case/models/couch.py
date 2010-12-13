from __future__ import absolute_import
from datetime import datetime, date, time
from couchdbkit.ext.django.schema import *
from corehq.apps.case import const
from dimagi.utils import parsing
from couchdbkit.schema.properties_proxy import SchemaListProperty
import logging
from datetime import datetime, date, time
from couchdbkit.ext.django.schema import *
from corehq.apps.case import const
from dimagi.utils import parsing
from couchdbkit.schema.properties_proxy import SchemaListProperty
import logging

"""
Couch models for commcare cases.  

For details on casexml check out:
http://bitbucket.org/javarosa/javarosa/wiki/casexml
"""

class CaseBase(Document):
    """
    Base class for cases and referrals.
    """
    opened_on = DateTimeProperty()
    modified_on = DateTimeProperty()
    type = StringProperty()
    closed = BooleanProperty(default=False)
    closed_on = DateTimeProperty()
    
    class Meta:
        app_label = 'case'

class CommCareCaseAction(Document):
    """
    An atomic action on a case. Either a create, update, or close block in
    the xml.  
    """
    action_type = StringProperty()
    date = DateTimeProperty()
    visit_date = DateProperty()
    
    @classmethod
    def from_action_block(cls, action, date, visit_date, action_block):
        if not action in const.CASE_ACTIONS:
            raise ValueError("%s not a valid case action!")
        
        action = CommCareCaseAction(action_type=action, date=date, visit_date=visit_date)
        
        # a close block can come without anything inside.  
        # if this is the case don't bother trying to post 
        # process anything
        if isinstance(action_block, basestring):
            return action
            
        action.type = action_block.get(const.CASE_TAG_TYPE_ID)
        action.name = action_block.get(const.CASE_TAG_NAME)
        if const.CASE_TAG_DATE_OPENED in action_block:
            action.opened_on = parsing.string_to_datetime(action_block[const.CASE_TAG_DATE_OPENED])
        
        for item in action_block:
            if item not in const.CASE_TAGS:
                action[item] = action_block[item]
        return action
    
    @classmethod
    def new_create_action(cls, date=None):
        """
        Get a new create action
        """
        if not date: date = datetime.utcnow()
        return CommCareCaseAction(action_type=const.CASE_ACTION_CLOSE, 
                                  date=date, visit_date=date.date(), 
                                  opened_on=date)
    
    @classmethod
    def new_close_action(cls, date=None):
        """
        Get a new close action
        """
        if not date: date = datetime.utcnow()
        return CommCareCaseAction(action_type=const.CASE_ACTION_CLOSE, 
                                  date=date, visit_date=date.date(),
                                  closed_on=date)
    
    class Meta:
        app_label = 'case'

    
class Referral(CaseBase):
    """
    A referral, taken from casexml.  
    """
    
    # Referrals have top-level couch guids, but this id is important
    # to the phone, so we keep it here.  This is _not_ globally unique
    # but case_id/referral_id/type should be.  
    # (in our world: case_id/referral_id/type)
    referral_id = StringProperty()
    followup_on = DateTimeProperty()
    outcome = StringProperty()
    
    class Meta:
        app_label = 'case'

    def __unicode__(self):
        return ("%s:%s" % (self.type, self.referral_id))
        
    def apply_updates(self, date, referral_block):
        if not const.REFERRAL_ACTION_UPDATE in referral_block:
            logging.warn("No update action found in referral block, nothing to be applied")
            return
        
        update_block = referral_block[const.REFERRAL_ACTION_UPDATE] 
        if not self.type == update_block[const.REFERRAL_TAG_TYPE]:
            raise logging.warn("Tried to update from a block with a mismatched type!")
            return
        
        if date > self.modified_on:
            self.modified_on = date
        
        if const.REFERRAL_TAG_FOLLOWUP_DATE in referral_block:
            self.followup_on = parsing.string_to_datetime(referral_block[const.REFERRAL_TAG_FOLLOWUP_DATE])
        
        if const.REFERRAL_TAG_DATE_CLOSED in update_block:
            self.closed = True
            self.closed_on = parsing.string_to_datetime(update_block[const.REFERRAL_TAG_DATE_CLOSED])
            
            
    @classmethod
    def from_block(cls, date, block):
        """
        Create referrals from a block of processed data (a dictionary)
        """
        if not const.REFERRAL_ACTION_OPEN in block:
            raise ValueError("No open tag found in referral block!")
        id = block[const.REFERRAL_TAG_ID]
        follow_date = parsing.string_to_datetime(block[const.REFERRAL_TAG_FOLLOWUP_DATE])
        open_block = block[const.REFERRAL_ACTION_OPEN]
        types = open_block[const.REFERRAL_TAG_TYPES].split(" ")
        
        ref_list = []
        for type in types:
            ref = Referral(referral_id=id, followup_on=follow_date, 
                            type=type, opened_on=date, modified_on=date, 
                            closed=False)
            ref_list.append(ref)
        
        # there could be a single update block that closes a referral
        # that we just opened.  not sure why this would happen, but 
        # we'll support it.
        if const.REFERRAL_ACTION_UPDATE in block:
            update_block = block[const.REFERRAL_ACTION_UPDATE]
            for ref in ref_list:
                if ref.type == update_block[const.REFERRAL_TAG_TYPE]:
                    ref.apply_updates(date, block)
        
        return ref_list

class CommCareCase(CaseBase):
    """
    A case, taken from casexml.  This represents the latest
    representation of the case - the result of playing all
    the actions in sequence.
    """
    
    case_id = StringProperty()
    external_id = StringProperty()
    encounter_id = StringProperty()
    
    referrals = SchemaListProperty(Referral)
    actions = SchemaListProperty(CommCareCaseAction)
    name = StringProperty()
    followup_type = StringProperty()
    
    # date the case actually starts, before this won't be sent to phone.
    # this is for missed appointments, which don't start until the appointment
    # is actually missed
    start_date = DateProperty()      
    activation_date = DateProperty() # date the phone triggers it active
    due_date = DateProperty()        # date the phone thinks it's due
    
    
    class Meta:
        app_label = 'case'
        
    def __unicode__(self):
        return "CommCareCase: %s (%s)" % (self.case_id, self.get_id)
    
    def get_version_token(self):
        """
        A unique token for this version. 
        """
        # in theory since case ids are unique and modification dates get updated
        # upon any change, this is all we need
        return "%(case_id)s::%(date_modified)s" % (self.case_id, self.date_modified)
    
    def is_started(self, since=None):
        """
        Whether the case has started (since a date, or today).
        """
        if since is None:
            since = date.today()
        return self.start_date <= since if self.start_date else True
    
    @classmethod
    def from_doc(cls, case_block):
        """
        Create a case object from a case block.
        """
        if not const.CASE_ACTION_CREATE in case_block:
            raise ValueError("No create tag found in case block!")
        
        # create case from required fields in the case/create block
        create_block = case_block[const.CASE_ACTION_CREATE]
        id = case_block[const.CASE_TAG_ID]
        opened_on = parsing.string_to_datetime(case_block[const.CASE_TAG_MODIFIED])
        
        # create block
        type = create_block[const.CASE_TAG_TYPE_ID]
        name = create_block[const.CASE_TAG_NAME]
        external_id = create_block[const.CASE_TAG_EXTERNAL_ID]
        user_id = create_block[const.CASE_TAG_USER_ID] if const.CASE_TAG_USER_ID in create_block else ""
        create_action = CommCareCaseAction.from_action_block(const.CASE_ACTION_CREATE, 
                                                             opened_on, opened_on.date(),
                                                             create_block)
        
        case = CommCareCase(case_id=id, opened_on=opened_on, modified_on=opened_on, 
                     type=type, name=name, user_id=user_id, external_id=external_id, 
                     closed=False, actions=[create_action,])
        
        # apply initial updates, referrals and such, if present
        case.update_from_block(case_block)
        return case
    
    @classmethod
    def get_by_case_id(cls, id):
        return cls.view(const.VIEW_BY_CASE_ID, key=id).one()
    
    def update_from_block(self, case_block, visit_date=None):
        
        mod_date = parsing.string_to_datetime(case_block[const.CASE_TAG_MODIFIED])
        if mod_date > self.modified_on:
            self.modified_on = mod_date
        
        # you can pass in a visit date, to override the udpate/close action dates
        if not visit_date:
            visit_date = mod_date.date()
        
        
        if const.CASE_ACTION_UPDATE in case_block:
            update_block = case_block[const.CASE_ACTION_UPDATE]
            update_action = CommCareCaseAction.from_action_block(const.CASE_ACTION_UPDATE, 
                                                                 mod_date, visit_date, 
                                                                 update_block)
            self.apply_updates(update_action)
            self.actions.append(update_action)
        
        if const.CASE_ACTION_CLOSE in case_block:
            close_block = case_block[const.CASE_ACTION_CLOSE]
            close_action = CommCareCaseAction.from_action_block(const.CASE_ACTION_CLOSE, 
                                                                mod_date, visit_date, 
                                                                close_block)
            self.apply_close(close_action)
            self.actions.append(close_action)
        
        if const.REFERRAL_TAG in case_block:
            referral_block = case_block[const.REFERRAL_TAG]
            if const.REFERRAL_ACTION_OPEN in referral_block:
                referrals = Referral.from_block(mod_date, referral_block)
                # for some reason extend doesn't work.  disconcerting
                # self.referrals.extend(referrals)
                for referral in referrals:
                    self.referrals.append(referral)
            elif const.REFERRAL_ACTION_UPDATE in referral_block:
                found = False
                update_block = referral_block[const.REFERRAL_ACTION_UPDATE]
                for ref in self.referrals:
                    if ref.type == update_block[const.REFERRAL_TAG_TYPE]:
                        ref.apply_updates(mod_date, referral_block)
                        found = True
                if not found:
                    logging.error(("Tried to update referral type %s for referral %s in case %s "
                                   "but it didn't exist! Nothing will be done about this.") % \
                                   update_block[const.REFERRAL_TAG_TYPE], 
                                   referral_block[const.REFERRAL_TAG_ID],
                                   self.case_id)
        
                        
        
        
    def apply_updates(self, update_action):
        """
        Applies updates to a case
        """
        if hasattr(update_action, "type") and update_action.type:
            self.type = update_action.type
        if hasattr(update_action, "name") and update_action.name:
            self.name = update_action.name
        if hasattr(update_action, "opened_on") and update_action.opened_on: 
            self.opened_on = update_action.opened_on
        
        for item in update_action.dynamic_properties():
            if item not in const.CASE_TAGS:
                self[item] = update_action[item]
        
    def apply_close(self, close_action):
        self.closed = True
        self.closed_on = datetime.combine(close_action.visit_date, time())


import corehq.apps.case.signals