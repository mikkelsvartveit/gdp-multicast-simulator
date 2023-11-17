class Node:
    def __init__(self, name, parent_router):
        self.name = name
        self.parent_router = parent_router
        self.neighbors = set()
        self.routing_table = {self: (None, 0)}

    def add_neighbor(self, neighbor, link_cost=1, reverse=False):
        self.neighbors.add(neighbor)

        # Add the neighbor itself to routing table unless there is already a shorter path to it
        if (
            neighbor not in self.routing_table
            or link_cost < self.routing_table[neighbor][1]
        ):
            self.routing_table[neighbor] = (neighbor, link_cost)

        # Check if the new neighbor has better paths to other nodes
        for destination, (_, distance_from_neighbor) in neighbor.routing_table.items():
            if (
                destination not in self.routing_table
                or distance_from_neighbor + link_cost
                < self.routing_table[destination][1]
            ):
                self.routing_table[destination] = (
                    neighbor,
                    distance_from_neighbor + link_cost,
                )

        # Register the neighborship on the other side. Do if check to avoid infinite loop
        if not reverse:
            neighbor.add_neighbor(self, link_cost, reverse=True)

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.name


class Client(Node):
    def __init__(self, name, switch):
        super().__init__(name, switch.parent_router)

        # Register the switch as a neighbor
        self.add_neighbor(switch)
        # Register this client as a neighbor in the switch
        switch.add_neighbor(self)


class Router(Node):
    def __init__(self, name, parent_router):
        super().__init__(name, parent_router)

        # Stuff below here is the RIB (lives inside the router)
        self.rib_nodes = set()
        self.rib_edges = set()
        self.rib_child_router_ownerships = {}
        self.rib_multicast_groups = {}

    def rib_add_link(self, node1, node2, link_cost):
        self.rib_nodes.add(node1)
        self.rib_nodes.add(node2)
        self.rib_edges.add((node1, node2, link_cost))


def main():
    routerRoot = Router("A", None)

    # Create trust domain with router and two switches, and two clients for each switch
    routerA = Router("routerA", parent_router=routerRoot)
    switch1 = Node("switch1", parent_router=routerA)
    switch1.add_neighbor(routerA)
    switch2 = Node("switch2", parent_router=routerA)
    switch2.add_neighbor(routerA)
    client1 = Client("client1", switch1)
    client2 = Client("client2", switch1)
    client3 = Client("client3", switch2)
    client4 = Client("client4", switch2)

    print("done")


main()
