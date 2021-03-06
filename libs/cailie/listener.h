
#ifndef CAILIE_LISTENER_H
#define CAILIE_LISTENER_H

#include <pthread.h>
#include <string>
#include <vector>
#include "state.h"

namespace ca {

class Process;

class Listener {
	public:
		Listener() : process_count(0), processes(NULL), listen_socket(0),
			thread(0), start_barrier(NULL), state(NULL){}
		void init(int port);
		void wait_for_connection();
		int get_port();

		void start();
		void main();
		void process_commands(FILE *comm_in, FILE *comm_out);

		void set_processes(int process_count, Process **processes) {
			this->process_count = process_count;
			this->processes = processes;
		}

		void set_start_barrier(pthread_barrier_t *barrier) {
			start_barrier = barrier;
		}

	protected:

		void prepare_state();
		void cleanup_state();
		void save_state();
		void save_first(State *s);
		void erase_others(int index);

		int listen_socket;
		int process_count;
		Process **processes;
		pthread_t thread;
		pthread_barrier_t *start_barrier;
		State *state;
		std::vector<std::string> sequence;

		//-------------------------------------------------

		std::vector<State*> History;
		State *FirstState;
};

}
#endif
