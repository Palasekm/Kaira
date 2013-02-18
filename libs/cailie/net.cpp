
#include "cailie.h"
#include <stdio.h>
#include <string.h>

using namespace ca;

NetDef::NetDef(int index, int id, SpawnFn *spawn_fn, bool local)
{
	this->index = index;
	this->id = id;
	this->spawn_fn = spawn_fn;
	this->local = local;
}

NetDef::~NetDef()
{
}

Transition * NetDef::make_transitions()
{
	Transition *ts = new Transition[transition_defs.size()];
	for (size_t i = 0; i < transition_defs.size(); i++) {
		ts[i].set_def(transition_defs[i]);
	}
	return ts;
}

void NetDef::register_transition(TransitionDef *transition_def)
{
	transition_defs.push_back(transition_def);
}

TransitionDef* NetDef::get_transition_def(int transition_id)
{
	for (size_t t = 0; t < transition_defs.size(); t++) {
		if (transition_defs[t]->get_id() == transition_id) {
			return transition_defs[t];
		}
	}
	return NULL;
}

NetBase * NetDef::spawn(ThreadBase *thread)
{
	return spawn_fn(thread, this);
}

Net::Net(NetDef *def, Thread *thread) :
	running_transitions(0),
	def(def),
	data(NULL),
	flags(0)
{
	if (thread->get_threads_count() > 1) {
		mutex = new pthread_mutex_t;
		pthread_mutex_init(mutex, NULL);
	} else {
		mutex = NULL;
	}
	transitions = def->make_transitions();
	activate_all_transitions();
}

Net::~Net()
{
	delete [] transitions;
	if (mutex) {
		pthread_mutex_destroy(mutex);
		delete mutex;
	}
}

void Net::activate_all_transitions()
{
	for (int t = 0; t < def->get_transitions_count(); t++) {
		activate_transition(&transitions[t]);
	}
}

void Net::activate_transition_by_pos_id(int pos_id)
{
	activate_transition(&transitions[pos_id]);
}

void Net::write_reports(Thread *thread, Output &output)
{
	write_reports_content(thread, output);
	int t;
	for (t = 0; t < def->get_transitions_count(); t++) {
		if (transitions[t].is_enable(thread, this)) {
			output.child("enabled");
			output.set("id", transitions[t].get_id());
			output.back();
		}
	}

}

Transition * Net::pick_active_transition()
{
	if (actives.empty()) {
		return NULL;
	}
	Transition *tr = actives.front();
	actives.pop();
	return tr;
}

int Net::fire_transition(Thread *thread, int transition_id)
{
	TransitionDef *tr = def->get_transition_def(transition_id);
	if (tr) {
		lock();
		int r = tr->full_fire(thread, this);
		if (r == NOT_ENABLED) {
			unlock();
		}
		return r;
	}
	return -1;
}

bool Net::is_something_enabled(Thread *thread)
{
	int t;
	for (t = 0; t < def->get_transitions_count(); t++) {
		if (transitions[t].is_enable(thread, this)) {
			return true;
		}
	}
	return false;
}

void Net::activate_transition(Transition *tr)
{
			if (tr->is_active()) {
				return;
			}
			CA_DLOG("Transition activated id=%i\n", tr->id);
			tr->set_active(true);
			actives.push(tr);
}
