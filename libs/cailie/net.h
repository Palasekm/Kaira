
#ifndef CAILIE_NET_H
#define CAILIE_NET_H

#include <queue>
#include <stdio.h>
#include <stdlib.h>
#include "output.h"
#include "packing.h"

namespace ca {

enum FireResult {
	NOT_ENABLED = 0,
	TRANSITION_FIRED
};

class NetBase;
class Net;
class NetDef;
class ThreadBase;
class Thread;
class Unpacker;

typedef NetBase * (SpawnFn)(ThreadBase *, NetDef *);

class TransitionDef {
	public:
		TransitionDef(int id, const std::string &name, bool immediate, int priority)
			 : id(id), immediate(immediate), priority(priority), name(name) {}
		virtual ~TransitionDef() {}

		int get_id() {
				return id;
		}

		int is_immediate() {
				return immediate;
		}

		int get_priority() {
				return priority;
		}

		const std::string& get_name() {
				return name;
		}

		virtual FireResult full_fire(ThreadBase *thread, NetBase *net) = 0;
		virtual FireResult full_fire_with_binding(ThreadBase *thread, NetBase *net, ca::Packer &packer) {
			fprintf(stderr, "Internal error: full_fire_with_binding\n");
			abort();
		};
		virtual void* fire_phase1(ThreadBase *thread, NetBase *net) = 0;
		virtual void fire_phase2(ThreadBase *thread, NetBase *net, void *data) = 0;
		virtual void fire_phase2_ro_binding
			(ThreadBase *thread, NetBase *net, void *data) = 0;
		virtual void cleanup_binding(void *data) = 0;
		virtual bool is_enable(ThreadBase *thread, NetBase *net) = 0;
		virtual void pack_binding(Packer &pack, void *data) {}

	protected:
		int id;
		bool immediate;
		int priority;
		std::string name;
};

class Transition {
	public:
		Transition() : active(false), def(NULL) {}

		void set_def(TransitionDef *def) {
				this->def = def;
		}

		bool is_active() {
				return active;
		}

		void set_active(bool value) {
				active = value;
		}

		int get_id() {
			return def->get_id();
		}

		int get_priority() {
			return def->get_priority();
		}

		int full_fire(ThreadBase *thread, NetBase *net) {
			return def->full_fire(thread, net);
		}

		bool is_enable(ThreadBase *thread, NetBase *net) {
			return def->is_enable(thread, net);
		}

		TransitionDef* get_def() {
			return def;
		}

	protected:
		bool active;
		TransitionDef *def;
};

class NetDef {

	public:
		NetDef(int index, int id, SpawnFn *spawn_fn, bool local);
		~NetDef();

		NetBase *spawn(ThreadBase *thread);
		void register_transition(TransitionDef *transition_def);
		TransitionDef* get_transition_def(int transition_id);
		Transition * make_transitions();

		int get_id() const {
			return id;
		}

		int get_index() const {
			return index;
		}

		bool is_local() const {
			return local;
		}

		int get_transitions_count() {
			return transition_defs.size();
		}

		const std::vector<TransitionDef*> & get_transition_defs() {
			return transition_defs;
		}

	protected:
		int index;
		int id;
		std::vector<TransitionDef*> transition_defs;
		SpawnFn *spawn_fn;
		bool local;
};

#define CA_NET_MANUAL_DELETE 1

class NetBase {
		public:
			virtual void receive(ThreadBase *thread, int process, int place, Unpacker &unpacker) = 0;
			virtual NetBase *copy() = 0;
			void write_reports(ThreadBase *thread, Output &output);

			virtual ~NetBase() { };
		protected:
			virtual void write_reports_content(ThreadBase *thread, Output &output) = 0;
};

class Net : public NetBase {
	public:
		Net(NetDef *def, Thread *thread);
		virtual ~Net();

		int fire_transition(Thread *thread, int transition_id);
		Transition * pick_active_transition();
		void activate_all_transitions();
		bool is_something_enabled(Thread *thread);

		int get_def_id() const {
			return def->get_id();
		}

		int get_def_index() const {
			return def->get_index();
		}

		NetDef *get_def() const {
			return def;
		}

		bool is_local() const {
			return def->is_local();
		}

		/* Lock for working with active_units */
		void lock() {
			if (mutex) pthread_mutex_lock(mutex);
		}

		bool try_lock() {
			return mutex?pthread_mutex_trylock(mutex) == 0:true;
		}

		void unlock() {
			if (mutex) pthread_mutex_unlock(mutex);
		}

		virtual NetDef *get_def() {
			return def;
		}

		void activate_transition_by_pos_id(int pos_id) {
			transitions[pos_id].set_active(true);
		}

		/* "manual delete" behaviour:
			net is not deleted automaticaly when it is quit and
			all threads remove its reference */
		void set_manual_delete() {
			flags |= CA_NET_MANUAL_DELETE;
		}

		bool get_manual_delete() {
			return flags & CA_NET_MANUAL_DELETE;
		}

	protected:
		NetDef *def;
		int running_transitions;
		pthread_mutex_t *mutex;
		Transition *transitions;

		void *data;
		int flags;
};

}

#endif // CAILIE_NET_H
