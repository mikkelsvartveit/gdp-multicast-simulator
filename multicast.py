from enum import Enum


class MessageTypes(Enum):
    RIB_QUERY_NEXT_HOP = 0
    RIB_ADD_LINK = 1
    RIB_ADD_OWNERSHIP = 2


class Message:
    def __init__(self, content, type: MessageTypes):
        self.content = content
        self.type: MessageTypes = type

    def __str__(self):
        return f"Message({self.type}, {self.content})"

    def __repr__(self):
        return f"Message({self.type}, {self.content})"


class Node:
    def __init__(self, name, parent_router):
        self.name = name
        self.parent_router = parent_router
        self.neighbors = set()
        self.routing_table = {self: (None, 0)}

    def get_next_hop(self, destination):
        # If not in the same trust domain, send to parent router instead
        if (
            destination != self.parent_router
            and self.parent_router != destination.parent_router
        ):
            return self.get_next_hop(self.parent_router)

        if destination not in self.routing_table:
            print(
                f"Destination {destination} not in routing table of {self}. Querying RIB"
            )

            # Query RIB for next hop
            message = Message(
                content=destination, type=MessageTypes["RIB_QUERY_NEXT_HOP"]
            )

            (next_hop, distance) = self.send_message(self, self.parent_router, message)

            self.routing_table[destination] = (next_hop, distance)

        return self.routing_table[destination][0]

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

        # Do if check to avoid back-and-forth recursion
        if not reverse:
            # Register neighborship on the other side
            neighbor.add_neighbor(self, link_cost, reverse=True)

            # Notify RIB of the new link
            message = Message(
                content=(self, neighbor, link_cost), type=MessageTypes.RIB_ADD_LINK
            )
            self.send_message(self, self.parent_router, message)

    def send_message(self, source, destination, message):
        next_hop = self.get_next_hop(destination=destination)
        return next_hop.receive_message(source, destination, message)

    def receive_message(self, source, destination, message):
        if self == destination:
            # Handle message
            self.handle_message(source, message)
        else:
            # Forward to next hop
            self.send_message(source, destination, message)

    def handle_message(self, source, message):
        print(f"[{self}] Message from {source}: {message}")

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.name


class Switch(Node):
    def __init__(self, name, parent_router):
        super().__init__(name, parent_router)

    def handle_message(self, source, message):
        super().handle_message(source, message)


class Client(Node):
    def __init__(self, name, switch):
        super().__init__(name, switch.parent_router)

        # Register the switch as a neighbor
        self.add_neighbor(switch)

    def handle_message(self, source, message):
        super().handle_message(source, message)


class Router(Node):
    def __init__(self, name, parent_router):
        super().__init__(name, parent_router)

        # Everything below here is the RIB (lives inside the router)
        self.rib_nodes = set()
        self.rib_edges = set()
        self.rib_child_router_ownerships = {}
        self.rib_multicast_groups = {}

    def handle_message(self, source, message):
        super().handle_message(source, message)

        if message.type == MessageTypes.RIB_ADD_LINK:
            (node1, node2, link_cost) = message.content
            self.rib_add_link(node1, node2, link_cost)

        elif message.type == MessageTypes.RIB_ADD_OWNERSHIP:
            (router, node) = message.content
            self.rib_add_ownership(router, node)

    def rib_add_link(self, node1, node2, link_cost):
        self.rib_nodes.add(node1)
        self.rib_nodes.add(node2)
        self.rib_edges.add((node1, node2, link_cost))

        # Propagate ownership up the tree
        if self.parent_router:
            message = Message(
                content=(self, node1), type=MessageTypes.RIB_ADD_OWNERSHIP
            )
            self.send_message(self, self.parent_router, message)

    def rib_add_ownership(self, router, node):
        if self != router:
            if not router in self.rib_child_router_ownerships:
                self.rib_child_router_ownerships[router] = set()
            self.rib_child_router_ownerships[router].add(node)

        # Propagate ownership up the tree
        if self.parent_router:
            message = Message(content=(self, node), type=MessageTypes.RIB_ADD_OWNERSHIP)
            self.send_message(self, self.parent_router, message)


def main():
    routerRoot = Router("routerRoot", None)

    # Create trust domain A with router and two switches, and two clients for each switch
    routerA = Router("routerA", parent_router=routerRoot)
    routerA.add_neighbor(routerRoot)
    switch1 = Switch("switch1", parent_router=routerA)
    switch1.add_neighbor(routerA)
    switch2 = Switch("switch2", parent_router=routerA)
    switch2.add_neighbor(routerA)
    client1 = Client("client1", switch1)
    client2 = Client("client2", switch1)
    client3 = Client("client3", switch2)
    client4 = Client("client4", switch2)

    # Create trust domain A with router and two switches, and two clients for each switch
    # Also add a switch between the two routers for the sake of it
    switchBridge = Switch("switchBridge", parent_router=routerRoot)
    switchBridge.add_neighbor(routerRoot)
    routerB = Router("routerB", parent_router=routerRoot)
    routerB.add_neighbor(switchBridge)
    switch3 = Switch("switch3", parent_router=routerB)
    switch3.add_neighbor(routerB)
    switch4 = Switch("switch4", parent_router=routerA)
    switch4.add_neighbor(routerA)
    client5 = Client("client5", switch3)
    client6 = Client("client6", switch3)
    client7 = Client("client7", switch4)
    client8 = Client("client8", switch4)
    # client8.send_message(client8, client7, Message("test", MessageTypes.RIB_ADD_LINK))

    print("done")


main()
