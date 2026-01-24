from pathlib import Path
import sqlite3
import logging
from datetime import datetime
from copy import deepcopy

log = logging.getLogger(__name__)

class FilterWrapper(dict):

    def filter_key(self, key):
        have_filter = '_do_not_serialize' in self.keys()
        if not have_filter:
            self['_do_not_serialize'] = []
        self['_do_not_serialize'].append(key)
        
    def items(self):
        have_filter = '_do_not_serialize' in self.keys()
        for k in self.keys():
            if  k == '_do_not_serialize':
                continue
            if have_filter and k in self['_do_not_serialize']:
                continue
            v = self[k]
            if isinstance(v, datetime): # The values that we want to exclude
                yield k, v.isoformat()
            elif not isinstance(v, TaskDB): # The values that we want to exclude
                yield k, v
    

class TrackingWrapper():

    def __init__(self, wrapped):
        self._wrapped = wrapped
        for key in [ key for key in wrapped.__dict__ if key != '_wrapped' ]:
            self._wrapped.__dict__["_orig_" + key] = self._wrapped.__dict__[key]

    def __getattr__(self, attr):
        if attr == '_wrapped':
            return self._wrapped
        return getattr(self._wrapped, attr)

    def __setattr__(self, attr, val):
        if attr == '_wrapped':
            super(TrackingWrapper, self).__setattr__('_wrapped', val)
        else:
            setattr(self._wrapped, attr, val)

    def is_changed(self):
        changes = self.get_changes()
        if len(changes) > 0:
            return True
        return False
            
    def get_changes(self):
        res = {}
        prop_names = [ key for key in self._wrapped.__dict__ if key != '_wrapped'
                       and not key.startswith('_orig')]
        for key in prop_names:
            orig = self._wrapped.__dict__["_orig_" + key]
            cur = self._wrapped.__dict__[key]
            if cur != orig :
                res[key] = dict(old=orig, new=cur)
        return res
            
    def revert(self):
        prop_names = [ key for key in self._wrapped.__dict__ if key != '_wrapped'
                       and not key.startswith('_orig')]
        for key in prop_names:
            orig = self._wrapped.__dict__["_orig_" + key]
            cur = self._wrapped.__dict__[key]
            # just in case there are side effects, only reset changed ones
            if cur != orig :
                 self._wrapped.__dict__[key] = orig

                 
class TaskRecord():

    def __init__(self, task_db, task_id, name, description, status,
                 project_id=None, phase_id=None, save_time=None):
        self.task_db = task_db
        self.task_id = task_id  # if is None, record is not in DB
        self.name = name
        self.description = description
        self.status = status
        self.project_id = project_id
        self.phase_id = phase_id
        self.save_time = save_time

    def __repr__(self):
        return f"task {self.task_id} {self.name[:20]}"

    def __eq__(self, other):
        if other and self.task_id:
            if self.task_id == other.task_id:
                return True
        return False
    
    def add_blocker(self, other_task):
        if other_task.task_id == self.task_id:
            raise Exception('would create loop')
        for other_need in other_task.get_blockers():
            if other_need.task_id == self.task_id:
                raise Exception('would create loop')
        self.task_db.add_task_blocker(self, other_task)
        
    def delete_blocker(self, other_task):
        self.task_db.delete_task_blocker(self, other_task)
        
    def get_blockers(self, descend=False, only_not_done=True):
        res = self.task_db.get_task_blockers(self, only_not_done=only_not_done)
        if descend:
            orig = res
            for rec in orig:
                more = rec.get_blockers(descend=True, only_not_done=only_not_done)
                for item in more:
                    if item not in res:
                        res.append(item)
        return res
        
    def blocks_tasks(self, ascend=False):
        res = self.task_db.get_tasks_blocked(self)
        if ascend:
            orig = res
            for rec in orig:
                more = self.task_db.get_tasks_blocked(rec)
                if len(more) > 0:
                    res += more
        return res
        
    def save(self):
        if self.phase_id and not self.project_id:
            self.project_id = self.phase.project_id
        new_rec = self.task_db.save_task_record(self)
        self.task_id = new_rec.task_id
        return True

    def get_tracking_wrapper(self):
        return TrackingWrapper(self)

    def delete_from_db(self):
        if self.task_id is not None:
            self.task_db.delete_task_record(self)
            self.task_id = None

    def add_to_project(self, project):
        self.project_id = project.project_id
        self.save()

    def add_to_phase(self, phase, move_to_project=False):
        phase_project = phase.project
        if self.project_id is not None and not move_to_project:
            proj = self.task_db.get_project_by_id(self.project_id)
            if phase_project is not proj:
                raise Exception(f'cannot add task to phase {phase}, it is not part of project {proj}')
        else:
            self.project_id = phase_project.project_id
        self.phase_id = phase.phase_id
        self.save()

    @property
    def project(self):
        if self.project_id:
            return self.task_db.get_project_by_id(self.project_id)
        return None

    @project.setter
    def project(self, value):
        if self.project_id is not value.project_id:
            if self.phase_id:
                self.phase_id = None
        self.project_id = value.project_id
        
    @property
    def phase(self):
        if self.phase_id:
            return self.task_db.get_phase_by_id(self.phase_id)
        return None

    @phase.setter
    def phase(self, value):
        self.phase_id = value.phase_id
        
    def to_json_dict(self):
        return FilterWrapper(self.__dict__)
    
class ProjectRecord():

    def __init__(self, task_db, project_id, name, description, parent=None,
                 parent_id=None, save_time=None):
        self.task_db = task_db
        self.project_id = project_id  # if is None, record is not in DB
        self.name = name
        self.description = description
        if parent:
            if parent_id and parent.project_id != parent_id:
                raise Exception('inconsistent parent project specs')
            self.parent_id = parent.project_id
        else:
            self.parent_id = parent_id
        self.save_time = save_time

    def __repr__(self):
        res = f"project {self.project_id} {self.name[:20]}"
        return res

    def __eq__(self, other):
        if other and self.project_id:
            if self.project_id == other.project_id:
                return True
        return False
    
    def save(self):
        new_rec = self.task_db.save_project_record(self)
        # in case this was initial save
        self.project_id = new_rec.project_id
        
    def get_kids(self):
        return self.task_db.get_projects_by_parent_id(self.project_id)
        
    def get_tasks(self):
        return self.task_db.get_tasks_for_project(self)
        
    @property
    def parent(self):
        if self.parent_id:
            return self.task_db.get_project_by_id(self.parent_id)
        return None

    @parent.setter
    def parent(self, value):
        self.parent_id = value.project_id
        
    def get_tracking_wrapper(self):
        return TrackingWrapper(self)

    def new_phase(self, name, description=None, follows=None):
        phases = self.get_phases()
        if follows:
            if follows not in phases:
                raise Exception('invalid follows spec on new phase, does not exist in project')
            follows_id = follows.phase_id
        else:
            follows_id = None

        return self.task_db.add_phase(name=name, description=description, project=self,
                                      follows_id=follows_id)
        
    def add_phase(self, phase, follows=None):
        phases = self.get_phases()
        follows_id = None
        if follows:
            if follows not in phases:
                raise Exception('invalid follows spec on new phase, does not exist in project')
            follows_id = follows.phase_id
        phase.project_id = self.project_id
        phase.follows_id = follows_id
        phase.save()
        return phase
        
    def get_phases(self):
        return self.task_db.get_phases_by_project_id(self.project_id)
    
    def delete_from_db(self):
        if self.project_id is None:
            return
        phases = self.get_phases()
        if self.parent_id:
            new_project = self.parent
        else:
            orphs = self.task_db.get_project_by_name('Orphans')
            if orphs is None:
                desc = "A project used to collect phases that are orphaned when "
                desc += "a project is deleted but still has phases. This is done "
                desc += "automatically. "

                orphs = self.task_db.add_project(name="Orphans",
                                                 description=desc)
            new_project = orphs
        
        if len(phases) == 0:
            self.task_db.replace_task_project_refs(self.project_id, new_project.project_id)
        else:
            for phase in phases:
                phase.change_project(new_project.project_id)
        self.task_db.delete_project_record(self)
        self.project_id = None
            
    def to_json_dict(self):
        return FilterWrapper(self.__dict__)
    
class PhaseRecord():

    def __init__(self, task_db, phase_id, name, description, project_id,
                 follows_id=None, save_time=None):
        self.task_db = task_db
        self.phase_id = phase_id  # if is None, record is not in DB
        self.name = name
        self.description = description
        self.project_id = project_id
        self.follows_id = follows_id
        self.save_time = save_time

    def __eq__(self, other):
        if other and self.phase_id:
            if self.phase_id == other.phase_id:
                return True
        return False

    def __repr__(self):
        res = f"phase {self.phase_id} {self.name[:20]}"
        return res

    @property
    def follows(self):
        if self.follows_id:
            return self.task_db.get_phase_by_id(self.follows_id)
        return None

    @follows.setter
    def follows(self, value):
        self.follows_id = value.phase_id
        
    @property
    def follower(self):
        return self.task_db.get_phase_that_follows(self.phase_id)
    
    @property
    def project(self):
        return self.task_db.get_project_by_id(self.project_id)

    @project.setter
    def project(self, value):
        self.project_id = value.project_id
        
    def save(self):
        new_rec =  self.task_db.save_phase_record(self)
        # in case this was initial save
        self.phase_id = new_rec.phase_id

    def get_tasks(self):
        return self.task_db.get_tasks_for_phase(self)
        
    def get_tracking_wrapper(self):
        return TrackingWrapper(self)

    def change_project(self, new_project_id):
        new_version = self.task_db.move_phase_and_tasks_to_project(self.phase_id, new_project_id)
        for key in new_version.__dict__:
            self.__dict__[key] = new_version.__dict__[key]
        
    def delete_from_db(self):
        if self.phase_id is None:
            return
        orig_id = self.phase_id 
        self.task_db.replace_task_phase_refs(orig_id, None)
        follower = self.task_db.get_phase_that_follows(orig_id)
        # can't make new link until old link is broken
        if follower:
            save_link_id = self.follows_id
            follower.follows_id = None
            follower.save()
        self.task_db.delete_phase_record(self)
        if follower:
            follower.follows_id = save_link_id
            follower.save()
        self.phase_id = None
            
    def to_json_dict(self):
        return FilterWrapper(self.__dict__)


    
class TaskDB():

    default_file_name = "task_db.sqlite"
    valid_status_values = ("ToDo", "Doing", "Done")
    
    def __init__(self, store_dir=".", name_override=None, autocreate=False):
        if name_override:
            name = name_override
        else:
            name = self.default_file_name
        self.store_dir = store_dir
        self.name = name
        self.filepath = Path(store_dir, name).resolve()
        self.db = None
        log.debug("new sqlite store for task db, not open yet")
        if not self.filepath.exists():
            if autocreate:
                self.open()
            else:
                raise Exception(f'no {name} file in {store_dir} and no autocreate')
        else:
            self.open()
            
    def open(self) -> None:
        self.db = sqlite3.connect(self.filepath,
                                  detect_types=sqlite3.PARSE_DECLTYPES |
                                  sqlite3.PARSE_COLNAMES)
        self.db.row_factory = sqlite3.Row
        cursor = self.db.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        self.db.commit()
        cursor.close()
        log.debug("created sqlite store for task_db")
        # harmless if already inited
        self.init_db()

    def init_db(self):
        cursor = self.db.cursor()
        log.debug("initializing project table in task db")
        schema =  "CREATE TABLE if not exists project ("
        schema += "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        schema += "name TEXT KEY NOT NULL UNIQUE, "
        schema += "name_lower TEXT KEY NOT NULL UNIQUE, "
        schema += "description TEXT NULL,"
        schema += "save_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "
        schema += "parent_id INTEGER REFERENCES project(id) ON DELETE CASCADE)"
        cursor.execute(schema)
        log.debug("initializing phase table in task db")
        schema =  "CREATE TABLE if not exists phase ("
        schema += "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        schema += "name TEXT KEY NOT NULL UNIQUE, "
        schema += "name_lower TEXT KEY NOT NULL UNIQUE, "
        schema += "description TEXT NULL,"
        schema += "project_id  INTEGER NOT NULL REFERENCES project(id), "
        schema += "position REAL NOT NULL, "
        schema += "save_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "
        schema += "follows INTEGER NULL REFERENCES phase(id))"
        cursor.execute(schema)
        log.debug("initializing task table in task db")
        schema =  "CREATE TABLE if not exists task ("
        schema += "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        schema += "name KEY TEXT NOT NULL UNIQUE, "
        schema += "name_lower KEY TEXT NOT NULL UNIQUE, "
        schema += "status TEXT NOT NULL, "
        schema += "project_id INTEGER REFERENCES project(id),"
        schema += "phase_id INTEGER REFERENCES phase(id),"
        schema += "save_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "
        schema += "description TEXT NULL)"
        cursor.execute(schema)
        log.debug("initializing blockers table in task db")
        schema =  "CREATE TABLE if not exists blockers ("
        schema += "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        schema += "item KEY INTEGER NOT NULL, "
        schema += "requires KEY INTEGER NOT NULL)"
        cursor.execute(schema)
        cursor.close()

    def make_backup(self, store_dir, filename):
        otb = TaskDB(store_dir, name_override=filename, autocreate=True)
        # if this seems funky, maybe it is, but it
        # allows the normal save code to do its normal
        # thing, instead of having to duplicate a lot
        # of it heare

        # Do it in multiple passes, setting up the projects first,
        # then iterating again to get the phases and tasks.
        # This allows handing of project parent/child relationships
        for project in self.get_projects():
            if project.parent_id is not None:
                continue
            project.task_db = otb
            project.project_id = None
            project.save()
        for project in self.get_projects():
            if project.parent_id is None:
                continue
            n_parent = otb.get_project_by_name(project.parent.name)
            project.task_db = otb
            project.project_id = None
            project.parent_id = n_parent.project_id
            project.save()
        for project in self.get_projects():
            new_project = otb.get_project_by_name(project.name)
            for phase in project.get_phases():
                phase.task_db = otb
                orig_phase_id = phase.phase_id
                phase.phase_id = None
                phase.project_id = new_project.project_id
                phase.save()
                # set it back to get tasks
                new_phase_id = phase.phase_id
                phase.phase_id = orig_phase_id
                phase.task_db = self
                for task in phase.get_tasks():
                    task.task_db = otb
                    task.task_id = None
                    task.project_id = new_project.project_id
                    task.phase_id = new_phase_id
                    task.save()
            for task in project.get_tasks():
                if task.phase_id is not None:
                    continue
                task.task_db = otb
                task.task_id = None
                task.project_id = new_project.project_id
                task.save()
        for o_task in self.get_tasks():
            n_task = otb.get_task_by_name(o_task.name)
            for o_b_task in o_task.get_blockers():
                n_b_task = otb.get_task_by_name(o_b_task.name)
                n_task.add_blocker(n_b_task)
                n_task.save()
        otb.close()
        return otb.filepath
    
    def add_task(self, name, description=None, status='ToDo', project_id=None, phase_id=None):
        cursor = self.db.cursor()
        sql = "select id from task where name_lower = ?"
        cursor.execute(sql, (name.lower(),))
        row = cursor.fetchone()
        if row:
            raise Exception(f"Already have a task named {name}")
        if status not in self.valid_status_values:
            raise Exception(f"Status not valid: {status}")
        if not project_id and phase_id:
            phase = self.get_phase_by_id(phase_id)
            project_id = phase.project_id
        sql =  "insert into task (name, name_lower, status, description, project_id, phase_id) "
        sql += "values (?, ?, ?, ?, ?, ?)"
        if description is None:
            description = ""
        cursor.execute(sql, (name, name.lower(), status, description, project_id, phase_id))
        self.db.commit()
        last_rowid = cursor.lastrowid
        cursor.close()
        return self.get_task_by_id(last_rowid)

    def get_task_by_name(self, name):
        cursor = self.db.cursor()
        sql = "select * from task where name_lower = ?"
        cursor.execute(sql, (name.lower(),))
        row = cursor.fetchone()
        cursor.close()
        if row:
            return TaskRecord(task_db=self, task_id=row['id'], name=row['name'],
                              description=row['description'], status=row['status'],
                              project_id=row['project_id'],
                              phase_id=row['phase_id'],
                              save_time=row['save_time'])
        return None

    def get_task_by_id(self, tid):
        cursor = self.db.cursor()
        sql = "select * from task where id = ?"
        cursor.execute(sql, (tid,))
        row = cursor.fetchone()
        cursor.close()
        if row:
            return TaskRecord(task_db=self, task_id=row['id'], name=row['name'],
                              description=row['description'], status=row['status'],
                              project_id=row['project_id'],
                              phase_id=row['phase_id'],
                              save_time=row['save_time'])
        return None

    def get_tasks(self):
        cursor = self.db.cursor()
        sql = "select * from task order by id"
        cursor.execute(sql)
        res = []
        for row in cursor.fetchall():
            rec = TaskRecord(task_db=self, task_id=row['id'], name=row['name'],
                             description=row['description'], status=row['status'],
                             project_id=row['project_id'],
                             phase_id=row['phase_id'],
                             save_time=row['save_time'])
            res.append(rec)
        cursor.close()
        return res

    def get_tasks_by_status(self, status):
        cursor = self.db.cursor()
        if status not in self.valid_status_values:
            raise Exception(f"Status not valid: {status}")
        sql = "select * from task where status = ? order by id"
        cursor.execute(sql, (status,))
        res = []
        for row in cursor.fetchall():
            rec = TaskRecord(task_db=self, task_id=row['id'], name=row['name'],
                             description=row['description'], status=row['status'],
                             project_id=row['project_id'],
                             phase_id=row['phase_id'],
                             save_time=row['save_time'])
            res.append(rec)
        cursor.close()
        return res

    def get_tasks_by_project_id(self, project_id):
        cursor = self.db.cursor()
        sql = "select * from task where project_id = ? order by id"
        cursor.execute(sql, (project_id,))
        res = []
        for row in cursor.fetchall():
            rec = TaskRecord(task_db=self, task_id=row['id'], name=row['name'],
                             description=row['description'], status=row['status'],
                             project_id=row['project_id'],
                             phase_id=row['phase_id'],
                             save_time=row['save_time'])
            res.append(rec)
        cursor.close()
        return res

    def move_phase_and_tasks_to_project(self, phase_id, new_project_id):
        cursor = self.db.cursor()
        cursor.execute("BEGIN TRANSACTION;")
        # find the end of the order and add this phase there
        sql = "select id, position from phase where project_id = ? order by position desc limit 1"
        cursor.execute(sql, (new_project_id,))
        row = cursor.fetchone()
        if not row:
            position = 1.0
        else:
            position = float(row['position']) + 1.0
            if row['id'] != phase_id:
                follows_id = row['id']
        sql = "update phase set project_id = ?, position = ?, save_time = CURRENT_TIMESTAMP where id = ?"
        cursor.execute(sql, (new_project_id, position, phase_id))
        sql = "update task set project_id = ?, save_time = CURRENT_TIMESTAMP  where phase_id = ?"
        cursor.execute(sql, (new_project_id, phase_id))
        cursor.execute("COMMIT;")
        self.db.commit()
        cursor.close()
        return self.get_phase_by_id(phase_id)
        
    def replace_task_project_refs(self, project_id, new_project_id):
        cursor = self.db.cursor()
        if new_project_id is not None:
            sql = "select * from project where id = ?"
            cursor.execute(sql, (new_project_id,))
            if cursor.fetchone() is None:
                raise Exception('Invalid project id')
        sql = "update task set project_id = ?, save_time = CURRENT_TIMESTAMP  where project_id = ?"
        cursor.execute(sql, (new_project_id, project_id))
        self.db.commit()
        cursor.close()

    def get_tasks_by_phase_id(self, phase_id):
        cursor = self.db.cursor()
        sql = "select * from task where phase_id = ? order by id"
        cursor.execute(sql, (phase_id,))
        res = []
        for row in cursor.fetchall():
            rec = TaskRecord(task_db=self, task_id=row['id'], name=row['name'],
                             description=row['description'], status=row['status'],
                             project_id=row['project_id'],
                             phase_id=row['phase_id'],
                             save_time=row['save_time'])
            res.append(rec)
        cursor.close()
        return res

    def replace_task_phase_refs(self, phase_id, new_phase_id):
        if phase_id == new_phase_id:
            return
        cursor = self.db.cursor()
        if new_phase_id is None:
            sql = "update task set phase_id = NULL, save_time = CURRENT_TIMESTAMP  where phase_id = ?"
            cursor.execute(sql, (phase_id,))
        else:
            # Not sure well ever use this. The similar code in project
            # is because of parent child, delete the child you move
            # all to parent. Not sure any similar mass move will make
            # sense for phases
            new_phase = self.get_phase_by_id(new_phase_id)
            if new_phase is None:
                raise Exception('Invalid phase id')
            sql = "update task set phase_id = ?, project_id = ?, save_time = CURRENT_TIMESTAMP "
            sql += "where phase_id = ?"
            cursor.execute(sql, (new_phase_id, new_phase.project.project_id, phase_id))
        self.db.commit()
        cursor.close()

    def save_task_record(self, record):
        cursor = self.db.cursor()
        if record.task_id is not None:
            cursor.execute("select * from task where id = ?", (record.task_id,))
            row = cursor.fetchone()
            if not row:
                raise Exception(f"Trying to save task with invalid task_id")
        sql = "select id from task where name_lower = ? "
        values = [record.name.lower(),]
        if record.task_id is not None:
            sql += "and id != ?"
            values.append(record.task_id)
        cursor.execute(sql, values)
        row = cursor.fetchone()
        if row:
            raise Exception(f"Already have a task named {name}")
        if record.phase_id:
            cursor.execute("select project_id from phase where id = ?", (record.phase_id,))
            row = cursor.fetchone()
            if not row:
                # would be caught by db, but we are here
                raise Exception(f"Trying to save task with invalid phase_id")
            if row['project_id'] != record.project_id:
                raise Exception(f"Task cannot be in phase but not in same project")
        values = [record.name, record.name.lower(), record.description,
                  record.status, record.project_id, record.phase_id]
        if record.task_id is None:
            sql = "insert into task (name, name_lower, description, "
            sql += "status, project_id, phase_id) values (?,?,?,?,?,?)"
        else:
            sql = "update task set name = ?, name_lower = ?, description = ?, status = ?, project_id = ?, "
            sql += "phase_id = ?, save_time = CURRENT_TIMESTAMP where id = ?"
            values.append(record.task_id)
        cursor.execute(sql, values)
        if record.task_id is None:
            record.task_id = cursor.lastrowid
        self.db.commit()
        cursor.close()
        return record

    def add_task_blocker(self, record, depends_on):
        cursor = self.db.cursor()
        sql = "select * from blockers where item == ? and requires = ?"
        cursor.execute(sql, (record.task_id, depends_on.task_id))
        row = cursor.fetchone()
        if row:
            return row['id']
        sql = "insert into blockers (item, requires) values (?,?)"
        cursor.execute(sql, (record.task_id, depends_on.task_id))
        res = cursor.lastrowid
        cursor.close()
        self.db.commit()
        return res

    def delete_task_blocker(self, record, depends_on):
        cursor = self.db.cursor()
        sql = "delete from blockers where item == ? and requires = ?"
        cursor.execute(sql, (record.task_id, depends_on.task_id))
        cursor.close()
        self.db.commit()

    def get_task_blockers(self, record, only_not_done=True):
        cursor = self.db.cursor()
        sql = "select requires from blockers where item == ?"
        cursor.execute(sql, (record.task_id,))
        res = []
        for row in cursor.fetchall():
            item = self.get_task_by_id(row[0])
            if only_not_done:
                if item.status != 'Done':
                    res.append(item)
            else:
                res.append(item)
        cursor.close()
        return res

    def get_tasks_blocked(self, record):
        cursor = self.db.cursor()
        sql = "select item from blockers where requires == ?"
        cursor.execute(sql, (record.task_id,))
        res = []
        for row in cursor.fetchall():
            res.append(self.get_task_by_id(row[0]))
        cursor.close()
        return res

    def delete_task_record(self, record):
        cursor = self.db.cursor()
        sql = "delete from task where id == ?"
        cursor.execute(sql, (record.task_id,))
        sql = "delete from blockers where requires == ? or item = ?"
        cursor.execute(sql, (record.task_id, record.task_id))
        self.db.commit()
        cursor.close()
        
    def add_project(self, name, description=None, parent_id=None, parent=None):
        cursor = self.db.cursor()
        sql = "select id from project where name_lower = ?"
        cursor.execute(sql, (name.lower(),))
        row = cursor.fetchone()
        if row:
            raise Exception(f"Already have a project named {name}")
        pid = None
        if parent_id is not None:
            pid = parent_id
        elif parent is not None:
            pid = parent.project_id
        if pid:
            sql = "select * from project where id = ?"
            cursor.execute(sql, (pid,))
            row = cursor.fetchone()
            if not row:
                raise Exception(f"Invalid parent id supplied")
        sql =  "insert into project (name, name_lower, description, parent_id) values (?, ?, ?, ?)"
        if description is None:
            description = ""
        cursor.execute(sql, (name, name.lower(), description, pid))
        self.db.commit()
        last_rowid = cursor.lastrowid
        cursor.close()
        rec = self.get_project_by_id(last_rowid)
        return rec
    
    def get_project_by_id(self, project_id):
        cursor = self.db.cursor()
        sql = "select * from project where id = ?"
        cursor.execute(sql, (project_id,))
        row = cursor.fetchone()
        cursor.close()
        if row:
            rec  =  ProjectRecord(task_db=self, project_id=row['id'],
                                  name=row['name'], description=row['description'],
                                  parent_id=row['parent_id'],
                                  save_time=row['save_time'])
            return rec
        return None

    def get_project_by_name(self, name):
        cursor = self.db.cursor()
        sql = "select * from project where name_lower = ?"
        cursor.execute(sql, (name.lower(),))
        row = cursor.fetchone()
        cursor.close()
        if row:
            rec  =  ProjectRecord(task_db=self, project_id=row['id'],
                                  name=row['name'], description=row['description'],
                                  parent_id=row['parent_id'],
                                  save_time=row['save_time'])
            return rec
        return None
    
    def get_projects(self):
        cursor = self.db.cursor()
        sql = "select * from project"
        cursor.execute(sql)
        res = []
        for row in cursor.fetchall():
            rec =  ProjectRecord(task_db=self, project_id=row['id'],
                                 name=row['name'], description=row['description'],
                                  parent_id=row['parent_id'],
                                  save_time=row['save_time'])
            res.append(rec)
        cursor.close()
        return res

    def get_projects_by_parent_id(self, parent_id):
        cursor = self.db.cursor()
        if parent_id:
            sql = "select * from project where parent_id = ?"
            cursor.execute(sql, (parent_id,))
        else:
            sql = "select * from project where parent_id is NULL"
            cursor.execute(sql)

        res = []
        for row in cursor.fetchall():
            rec =  ProjectRecord(task_db=self, project_id=row['id'],
                                 name=row['name'], description=row['description'],
                                 parent_id=row['parent_id'],
                                  save_time=row['save_time'])
            res.append(rec)
        cursor.close()
        return res

    def save_project_record(self, record):
        cursor = self.db.cursor()
        if record.project_id is not None:
            cursor.execute("select * from project where id = ?", (record.project_id,))
            row = cursor.fetchone()
            if not row:
                raise Exception(f"Trying to save project with invalid project_id")
        sql = "select id from project where name_lower = ? "
        values = [record.name.lower(),]
        if record.project_id is not None:
            sql += "and id != ?"
            values.append(record.project_id)
        cursor.execute(sql, values)
        row = cursor.fetchone()
        if row:
            raise Exception(f"Already have a project named {name}")
        parent_id = None
        if record.parent_id:
            parent_id = record.parent_id
        values = [record.name, record.name.lower(), record.description, parent_id,]
        if record.project_id is None:
            sql = "insert into project (name, name_lower, description, parent_id) values (?,?,?,?)"
        else:
            sql = "update project set name = ?, name_lower = ?, description = ?, parent_id = ?, "
            sql += "save_time = CURRENT_TIMESTAMP where id = ?"
            values.append(record.project_id)
        cursor.execute(sql, values)
        if record.project_id is None:
            record.project_id = cursor.lastrowid
        self.db.commit()
        cursor.close()
        return record

    def get_tasks_for_project(self, record):
        if record.project_id is None:
            return []
        return self.get_tasks_by_project_id(record.project_id)
    
    def delete_project_record(self, record):
        cursor = self.db.cursor()
        sql = "delete from project where id == ?"
        cursor.execute(sql, (record.project_id,))
        self.db.commit()
        cursor.close()

    def add_phase(self, name, description=None, project_id=None, project=None, follows_id=None):
        return self.save_phase(name=name, description=description, phase_id=None, 
                               project_id=project_id, project=project, follows_id=follows_id)
    
    def save_phase(self, name, description=None, phase_id=None,
                   project_id=None, project=None, follows_id=None):
        cursor = self.db.cursor()
        sql = "select id from phase where name_lower = ?"
        cursor.execute(sql, (name.lower(),))
        row = cursor.fetchone()
        if row:
            # could be saving a new record, or saving existing.
            if row['id'] != phase_id:
                raise Exception(f"Already have a phase named {name}")
        pid = None
        if project_id is None and project is None:
            raise Exception('phases must have a project')
        if project is None:
            project = self.get_project_by_id(project_id)
        else:
            # caller  might be inconsistent, let's ignore it
            project_id = project.project_id
        sql = "select * from project where id = ?"
        cursor.execute(sql, (project_id,))
        row = cursor.fetchone()
        if not row:
            raise Exception(f"Invalid project id supplied")
            raise Exception(f"Invalid project id supplied")

        if follows_id is None:
            # This will be the common case for inserting new records, they
            # go on the end of the list. We record the order of the list with the
            # position column, and use a float so that we can arrange inserts to
            # leave lots of room for reordering by using the space between integers
            # Runs out of space after about 100 inserts between the same integers. Be surprised
            # if we hit that in practice.
            sql = "select id, position from phase where project_id = ? order by position desc limit 1"
            cursor.execute(sql, (project_id,))
            row = cursor.fetchone()
            if not row:
                position = 1.0
            else:
                position = float(row['position']) + 1.0
                if row['id'] != phase_id:
                    follows_id = row['id']
        else: 
            if follows_id == phase_id:
                raise Exception('phase cannot follow itself')
            sql = "select * from phase where id = ?"
            cursor.execute(sql, (follows_id,))
            follows_row = cursor.fetchone()
            if not follows_row:
                raise Exception(f"Invalid phase id supplied for follows property")
            if follows_row['project_id'] != project_id:
                raise Exception(f"Phase linking through follows property limited to same project")
            # all valid, now see if we are inserting into the list or appending
            sql = "select id, position from phase where project_id = ? "
            values = [project_id,]
            if phase_id:
                sql += " and id != ? "
                values.append(phase_id)
            sql += "and position > ? order by position limit 1"
            values.append(follows_row['position'])
            cursor.execute(sql, values)
            next_row = cursor.fetchone()
            if not next_row:
                position = float(follows_row['position']) + 1.0
            else:
                offset = (float(next_row['position']) - float(follows_row['position'])) * 0.75
                position = float(follows_row['position']) + offset
        if phase_id is None:
            sql =  "insert into phase (name, name_lower, description, project_id, position) "
            sql += "values (?, ?, ?, ?, ?)"
            values = (name, name.lower(), description, project_id, position)
            cursor.execute(sql, values)
            new_phase_id = cursor.lastrowid
        else:
            # make sure supplied id is not bogus
            sql =  "select name from phase where id = ?"
            cursor.execute(sql, (phase_id,))
            row = cursor.fetchone()
            if not row:
                raise Exception("Supplied phase_id does not exist")
            sql =  "update phase set name = ?, name_lower = ?, description = ?, project_id = ?, position = ?, "
            sql += "save_time = CURRENT_TIMESTAMP where id = ?"
            values = (name, name.lower(), description, project_id, position, phase_id)
            cursor.execute(sql, values)
            new_phase_id = phase_id
        self.db.commit()
        cursor.close()
        rec = self.get_phase_by_id(new_phase_id)
        return rec
            
    def row_to_phase(self, cursor, row):
        rec  = PhaseRecord(task_db=self, phase_id=row['id'],
                           name=row['name'], description=row['description'],
                           project_id=row['project_id'],
                           save_time=row['save_time'])
        sql = "select * from phase where project_id = ? and position < ? order by position desc limit 1"
        cursor.execute(sql, [row['project_id'], row['position'],])
        f_row = cursor.fetchone()
        if f_row:
            rec.follows_id = f_row['id']
        return rec
    
    def get_phase_by_id(self, phase_id):
        cursor = self.db.cursor()
        sql = "select * from phase where id = ?"
        cursor.execute(sql, (phase_id,))
        row = cursor.fetchone()
        if not row:
            cursor.close()
            return None
        rec = self.row_to_phase(cursor, row)
        cursor.close()
        return rec

    def get_phase_by_name(self, name):
        cursor = self.db.cursor()
        sql = "select * from phase where name_lower = ?"
        cursor.execute(sql, (name.lower(),))
        row = cursor.fetchone()
        if not row:
            cursor.close()
            return None
        rec = self.row_to_phase(cursor, row)
        cursor.close()
        return rec

    def get_phases_by_project_id(self, project_id, follow_order=True):
        cursor = self.db.cursor()
        sql = "select * from phase where project_id = ? order by position"
        cursor.execute(sql, (project_id,))
        res = []
        project = None
        new_cursor = self.db.cursor()
        for row in cursor.fetchall():
            rec = self.row_to_phase(new_cursor, row)
            res.append(rec)
        new_cursor.close()
        cursor.close()
        return res

    def get_phase_that_follows(self, follows_phase_id):
        cursor = self.db.cursor()
        sql = "select project_id, position from phase where id = ?"
        cursor.execute(sql, (follows_phase_id,))
        row = cursor.fetchone()
        if row is None:
            cursor.close()
            return None
        project_id = row[0]
        position = row[1]
        sql = "select * from phase where project_id = ? and position > ? order by position limit 1"
        cursor.execute(sql, (project_id, position,))
        row = cursor.fetchone()
        if not row:
            cursor.close()
            return None
        rec = self.row_to_phase(cursor, row)
        cursor.close()
        return rec
        
    def save_phase_record(self, record):
        return self.save_phase(name=record.name, description=record.description,
                               phase_id=record.phase_id, project=record.project,
                               follows_id=record.follows_id)
        

    def get_tasks_for_phase(self, record):
        if record.phase_id is None:
            return []
        return self.get_tasks_by_phase_id(record.phase_id)
    
    def delete_phase_record(self, record):
        cursor = self.db.cursor()
        sql = "delete from phase where id == ?"
        cursor.execute(sql, (record.phase_id,))
        self.db.commit()
        cursor.close()

    def close(self):
        self.db.close()
        self.db = None

