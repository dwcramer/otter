USE @@KEYSPACE@@;

-- Desired underlying structure is for the row key to be
-- the account ID, the column key to be the group ID, with
-- the data contained as JSON
--
-- In CQL3, the primary key is split such that the first part
-- ends up in the row key, the rest of the key ends up
-- as a composite column key.
--
-- This does a good job of making things a bit more rational
-- than some of the CQL2 ecentricity.
--
-- My mother, who cut her teeth in those heady days of IMS
-- and mainframe computers, before Codd's relational model
-- will probably get the giggles looking at this.

-- group_config is json blob
--
-- launch_config is json blob
--
-- active is the active list.
-- format:
--   {"instanceid: {"name": "servername", "links": json_links_obj, "created": date}}
--
-- pending is the pending list.
-- format:
--  {"jobid": {"created": date}}
--
-- groupTouched is a timestamp of the last time a scaling policy
--  was executed in the group
--
-- policyTouched is a list of timestamps for the policy
--  {"policyid": date}
--
-- declaring a variable as an int means that it is a 32-bit signed int.
-- declaring it as a varint means that it is an arbitrary precision int, which
-- is more general.  If there is no particular need for an int to be one thing
-- or another, varint is preferred.

CREATE COLUMNFAMILY scaling_group (
    "tenantId" ascii,
    "groupId" ascii,
    group_config ascii,
    launch_config ascii,
    desired varint,
    active ascii,
    pending ascii,
    "groupTouched" ascii,
    "policyTouched" ascii,
    paused boolean,
    created_at timestamp,
    PRIMARY KEY("tenantId", "groupId")
) WITH compaction = {
    'class' : 'SizeTieredCompactionStrategy',
    'min_threshold' : '2'
} AND gc_grace_seconds = 3600;
