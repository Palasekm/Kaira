
#include <alloca.h>
#include <stdio.h>

#include "cailie.h"

void CaProcess::multisend(int target, CaNet *net, int place_pos, int tokens_count, const CaPacker &packer, CaThread *thread)
{
	std::vector<int> a(1);
	a[0] = target;
	multisend_multicast(a, net, place_pos, tokens_count, packer, thread);
	/*
	#ifdef CA_MPI
		CaPacket *packet = (CaPacket*) packer.get_buffer();
		packet->unit_id = unit_id;
		packet->place_pos = place_pos;
		eacket->tokens_count = tokens_count;
		path.copy_to_mem(packet + 1);
		MPI_Request *request = requests.new_request(buffer);
		MPI_Isend(packet, packer.get_size(), MPI_CHAR, path.owner_id(process, unit_id), CA_MPI_TAG_TOKENS, MPI_COMM_WORLD, request);
	#else
	#endif */
}

void CaProcess::process_packet(CaThread *thread, int tag, void *data)
{
	if (tag == CA_TAG_SERVICE) {
		process_service_message(thread, (CaServiceMessage*) data);
		free(data);
		return;
	}
	CaTokens *tokens = (CaTokens*) data;
	if(!is_future_id(tokens->net_id)) {
		CA_DLOG("Too early message on process=%d net_id=%d\n", get_process_id(), tokens->net_id);
		too_early_message[tokens->net_id].push_back(data);
		return;
	}
	CaUnpacker unpacker(tokens + 1);
	CaNet *n = thread->get_net(tokens->net_id);
	if (n == NULL) {
		CA_DLOG("Net not found net=%i process=%i thread=%i\n",
			tokens->net_id, get_process_id(), thread->get_id());
		// Net is already stopped therefore we can throw tokens away
		return;
	}
	n->lock();
	int place_index = tokens->place_index;
	int tokens_count = tokens->tokens_count;
	CA_DLOG("RECV net=%i index=%i process=%i thread=%i\n",
		tokens->net_id, place_index, get_process_id(), thread->get_id());
	for (int t = 0; t < tokens_count; t++) {
		n->receive(place_index, unpacker);
	}
	CA_DLOG("EOR index=%i process=%i thread=%i\n", place_index, get_process_id(), thread->get_id());
	n->unlock();
	free(data);
}

void CaProcess::process_service_message(CaThread *thread, CaServiceMessage *smsg)
{
	switch (smsg->type) {
		case CA_SM_QUIT:
			CA_DLOG("SERVICE CA_SM_QUIT on process=%i thread=%i\n", get_process_id(), thread->get_id());
			too_early_message.clear();
			quit();
			break;
		case CA_SM_NET_CREATE:
		{
			CA_DLOG("SERVICE CA_SM_NET_CREATE on process=%i thread=%i\n", get_process_id(), thread->get_id());
			CaServiceMessageNetCreate *m = (CaServiceMessageNetCreate*) smsg;
			if(halted_net.count(m->net_id)) {
				CA_DLOG("Stop creating halted net on process=%i thread=%i\n", get_process_id(), thread->get_id());
				update_net_id_counters(m->net_id);
				too_early_message.erase(m->net_id);
				halted_net.erase(m->net_id);
				break;
			}
			CaNet *net = spawn_net(thread, m->def_index, m->net_id, NULL, false);
			net->unlock();
			if(too_early_message.count(m->net_id)) {
				std::vector<void* >::const_iterator i;
				for (i = too_early_message[m->net_id].begin(); i != too_early_message[m->net_id].end(); i++) {
					process_packet(thread, CA_TAG_TOKENS, *i);
				}
				too_early_message.erase(m->net_id);
			}
			break;
		}
		case CA_SM_NET_HALT:
		{
			CA_DLOG("SERVICE CA_SM_NET_HALT on process=%i thread=%i\n", get_process_id(), thread->get_id());
			CaServiceMessageNetHalt *m = (CaServiceMessageNetHalt*) smsg;
			if(!is_future_id(m->net_id)) {
				CA_DLOG("Halting not created net on process=%d net_id=%d\n", get_process_id(), tokens->net_id);
				halted_net.insert(m->net_id);
			}
			inform_halt_network(m->net_id, thread);
			break;
		}
		case CA_SM_WAKE:
		{
			CA_DLOG("SERVICE CA_SM_WAKE on process=%i thread=%i\n", get_process_id(), thread->get_id());
			start_and_join();
			clear();
			#ifdef CA_MPI
			MPI_Barrier(MPI_COMM_WORLD);
			#endif
			break;
		}
		case CA_SM_EXIT:
			CA_DLOG("SERVICE CA_SM_EXIT on process=%i thread=%i\n", get_process_id(), thread->get_id());
			too_early_message.clear();
			halted_net.clear();
			free(smsg);
			exit(0);
	}
}

CaNet * CaProcess::spawn_net(CaThread *thread, int def_index, int id, CaNet *parent_net, bool globally)
{
	CA_DLOG("Spawning id=%i def_id=%i parent_net=%i globally=%i\n",
		id, def_index, parent_net?parent_net->get_id():-1, globally);
	if (globally && !defs[def_index]->is_local()) {
		CaServiceMessageNetCreate *m =
			(CaServiceMessageNetCreate *) alloca(sizeof(CaServiceMessageNetCreate));
		m->type = CA_SM_NET_CREATE;
		m->net_id = id;
		m->def_index = def_index;
		broadcast_packet(CA_TAG_SERVICE, m, sizeof(CaServiceMessageNetCreate), thread, process_id);
	}

	CaNet *net = defs[def_index]->spawn(thread, id, parent_net);
	net->lock();
	update_net_id_counters(net->get_id());
	inform_new_network(net, thread);
	return net;
}

void CaProcess::update_net_id_counters(int net_id)
{
	int src_proc = net_id % process_count;
	CA_DLOG("Update process id counter, process=%d, net_id=%d\n", process_id, net_id);
	if(process_id_counter[src_proc] < net_id) {
		process_id_counter[src_proc] = net_id;
	}
}

bool CaProcess::is_future_id(int net_id)
{
	int last_net, src_proc = net_id % process_count;
	last_net = process_id_counter[src_proc];
	if (last_net < net_id) {
		return false;
	} else {
		return true;
	}
}

CaProcess::CaProcess(int process_id, int process_count, int threads_count, int defs_count, CaNetDef **defs)
{
	this->id_counter = process_id + process_count;
	this->process_id = process_id;
	this->process_count = process_count;
	this->defs_count = defs_count;
	this->defs = defs;
	this->threads_count = threads_count;
	pthread_mutex_init(&counter_mutex, NULL);
	process_id_counter = new int[process_count];
	for(int i = 0 ; i < process_count ; i++)
	{
		process_id_counter[i] = -1;
	}
	threads = new CaThread[threads_count];
	// TODO: ALLOCTEST
	int t;
	for (t = 0; t < threads_count; t++) {
		threads[t].set_process(this, t);
	}

	#ifdef CA_SHMEM
	this->packets = NULL;
	pthread_mutex_init(&packet_mutex, NULL);
	#endif
}

int CaProcess::new_net_id()
{
	pthread_mutex_lock(&counter_mutex);
	id_counter += process_count;
	int id = id_counter;
	pthread_mutex_unlock(&counter_mutex);
	return id;
}

CaProcess::~CaProcess()
{
	delete [] threads;
	pthread_mutex_destroy(&counter_mutex);
	delete [] process_id_counter;

	#ifdef CA_SHMEM
	pthread_mutex_destroy(&packet_mutex);
	#endif
}

void CaProcess::start()
{
	quit_flag = false;

	int t;
	for (t = 0; t < threads_count; t++) {
		threads[t].start();
	}
}

void CaProcess::join()
{
	int t;
	for (t = 0; t < threads_count; t++) {
		threads[t].join();
	}
}

void CaProcess::start_and_join()
{
	if (threads_count == 1) {
		// If there is only one process them process thread runs scheduler,
		// it is important because if threads_count == 1 we run MPI in MPI_THREAD_FUNELLED mode
		quit_flag = false;
		threads[0].run_scheduler();
	} else {
		start();
		join();
	}
}

void CaProcess::clear()
{
	for(int i = threads_count - 1 ; i >= 0 ; i--)
	{
		get_thread(i)->clear();
	}
}

CaThread * CaProcess::get_thread(int id)
{
	return &threads[id];
}

void CaProcess::inform_new_network(CaNet *net, CaThread *thread)
{
	for (int t = 0; t < threads_count; t++) {
		if (thread && thread->get_id() == t) {
			CaThreadMessageNewNet msg(net);
			msg.process(thread);
		} else {
			threads[t].add_message(new CaThreadMessageNewNet(net));
		}
	}
}

void CaProcess::inform_halt_network(int net_id, CaThread *thread)
{
	for (int t = 0; t < threads_count; t++) {
		if (thread && thread->get_id() == t) {
			CaThreadMessageHaltNet msg(net_id);
			msg.process(thread);
		} else {
			threads[t].add_message(new CaThreadMessageHaltNet(net_id));
		}
	}
}

void CaProcess::send_barriers(pthread_barrier_t *barrier1, pthread_barrier_t *barrier2)
{
	for (int t = 0; t < threads_count; t++) {
		threads[t].add_message(new CaThreadMessageBarriers(barrier1, barrier2));
	}
}

void CaProcess::quit_all(CaThread *thread)
{
	CaServiceMessage *m = (CaServiceMessage*) alloca(sizeof(CaServiceMessage));
	m->type = CA_SM_QUIT;
	broadcast_packet(CA_TAG_SERVICE, m, sizeof(CaServiceMessage), thread, process_id);
	quit();
}

void CaProcess::write_reports(FILE *out) const
{
	CaOutput output;
	output.child("process");
	output.set("id", process_id);
	output.set("running", !quit_flag);

	std::vector<CaNet*>::const_iterator i;
	const std::vector<CaNet*> &nets = threads[0].get_nets();
	for (i = nets.begin(); i != nets.end(); i++) {
		(*i)->write_reports(&threads[0], output);
	}
	CaOutputBlock *block = output.back();
	block->write(out);
	delete block;
}

// Designed for calling during simulation
void CaProcess::autohalt_check(CaNet *net)
{
	if (net->is_autohalt() && net->get_running_transitions() == 0
			&& !net->is_something_enabled(&threads[0])) {
			CaNet *parent = net->get_parent_net();
			/* During normal run net is finalized after halt in processing thread message
				But we dont want to wait for message processing because we want
				need right value of get_running_transitions in parent net */
			net->finalize(&threads[0]);
			halt(&threads[0], net);
			if (parent) {
				autohalt_check(parent);
			}
	}
}

// Designed for calling during simulation
void CaProcess::fire_transition(int transition_id, int instance_id)
{
	std::vector<CaNet*>::const_iterator i;
	const std::vector<CaNet*> &nets = threads[0].get_nets();
	for (i = nets.begin(); i != nets.end(); i++) {
		CaNet *n = *i;
		if (n->get_id() == instance_id) {
			if (n->fire_transition(&threads[0], transition_id)
				== CA_TRANSITION_FIRED_WITH_MODULE) {
				// Module was started so we have to checked if it is not dead from start
				threads[0].process_messages();
				n = threads[0].last_net();
			}
			autohalt_check(n);
			return;
		}
	}
}

/* 	Halt net net, sends information about halting if net is nonlocal
	Function inform_halt_network must send thread message to yourself, instance of net isn't free
	instantly, this is the reason why second argument is NULL */
void CaProcess::halt(CaThread *thread, CaNet *net)
{
	if (!net->is_local()) {
		CaServiceMessageNetHalt *m =
			(CaServiceMessageNetHalt*) alloca(sizeof(CaServiceMessageNetHalt));
		m->type = CA_SM_NET_HALT;
		m->net_id = net->get_id();
		broadcast_packet(CA_TAG_SERVICE, m, sizeof(CaServiceMessageNetHalt), thread, process_id);
	}
	inform_halt_network(net->get_id(), NULL);
}


