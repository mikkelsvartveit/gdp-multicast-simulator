from enum import Enum

# Enable to print every message received at any node. Disable to only print messages received at clients.
DEBUG = False


class MessageTypes(Enum):
    PING = 0
    RIB_ADD_LINK = 1
    RIB_ADD_OWNERSHIP = 2
    RIB_QUERY_NEXT_HOP = 3
    MULTICAST_CREATE_GROUP = 4
    MULTICAST_JOIN_GROUP = 5
    RIB_QUERY_NEXT_MULTICAST_HOPS = 6


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
        self.multicast_routing_table = {}

    def get_next_hop(self, destination):
        if destination not in self.routing_table:
            # print(f"[{self}] {destination} not in routing table. Querying RIB...")

            # Query RIB for next hop
            message = Message(
                content=destination, type=MessageTypes["RIB_QUERY_NEXT_HOP"]
            )

            (next_hop, distance) = self.send_message(self, self.parent_router, message)

            self.routing_table[destination] = (next_hop, distance)

        return self.routing_table[destination]

    def get_next_multicast_hops(self, multicast_group):
        if multicast_group not in self.multicast_routing_table:
            # print(
            #     f"[{self}] {multicast_group} not in multicast routing table. Querying RIB..."
            # )

            # Query RIB for next hop
            message = Message(
                content=multicast_group,
                type=MessageTypes["RIB_QUERY_NEXT_MULTICAST_HOPS"],
            )

            next_hops = self.send_message(self, self.parent_router, message)

            self.multicast_routing_table[multicast_group] = next_hops

        return self.multicast_routing_table[multicast_group]

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
        next_hop = self.get_next_hop(destination=destination)[0]
        return next_hop.receive_message(source, destination, message)

    def receive_message(self, source, destination, message):
        if self == destination:
            # Handle message
            return self.handle_message(source, message)
        else:
            # Forward to next hop
            return self.send_message(source, destination, message)

    def send_multicast_message(self, source, multicast_group, message, visited=set()):
        next_hops = self.get_next_multicast_hops(multicast_group)
        updated_visited = visited.copy()
        updated_visited.add(self)
        return [
            next_hop.receive_multicast_message(
                source, multicast_group, message, updated_visited
            )
            for next_hop in next_hops
            if next_hop not in visited
        ]

    def receive_multicast_message(self, source, multicast_group, message, visited):
        if (
            hasattr(self, "multicast_groups")
            and multicast_group in self.multicast_groups
        ):
            # Handle message
            return self.handle_message(source, message)
        else:
            # Forward to next hops
            return self.send_multicast_message(
                source, multicast_group, message, visited
            )

    def handle_message(self, source, message):
        print(f"[{self}] Received message from {source}: {message}")

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.name


class Switch(Node):
    def __init__(self, name, parent_router):
        super().__init__(name, parent_router)


class Client(Node):
    def __init__(self, name, switch):
        super().__init__(name, switch.parent_router)
        self.multicast_groups = set()

        # Register the switch as a neighbor
        self.add_neighbor(switch)

    def handle_message(self, source, message):
        super().handle_message(source, message)

    def create_multicast_group(self, group_name):
        message = Message(content=group_name, type=MessageTypes.MULTICAST_CREATE_GROUP)
        self.send_message(self, self.parent_router, message)
        self.multicast_groups.add(group_name)

    def join_multicast_group(self, group_name):
        message = Message(content=group_name, type=MessageTypes.MULTICAST_JOIN_GROUP)
        response = self.send_message(self, self.parent_router, message)
        self.multicast_groups.add(group_name)


class Router(Node):
    def __init__(self, name, parent_router):
        super().__init__(name, parent_router)

        # Everything below here is the RIB (lives inside the router)
        self.rib_nodes = set()
        self.rib_edges = set()
        self.rib_child_router_ownerships = {}
        self.rib_multicast_groups = {}

    def get_next_hop(self, destination):
        if destination not in self.routing_table:
            # print(
            #     f"[{self}] {destination} not in routing table of {self}. Querying RIB..."
            # )

            # Query RIB for next hop
            (next_hop, distance) = self.rib_query_next_hop(self, destination)

            self.routing_table[destination] = (next_hop, distance)

        return self.routing_table[destination]

    def get_next_multicast_hops(self, multicast_group):
        if multicast_group not in self.multicast_routing_table:
            # print(
            #     f"[{self}] {multicast_group} not in multicast routing table. Querying RIB..."
            # )

            # Query RIB for next hop
            next_hops = self.rib_query_next_multicast_hops(self, multicast_group)

            self.multicast_routing_table[multicast_group] = next_hops

        return self.multicast_routing_table[multicast_group]

    def handle_message(self, source, message):
        if DEBUG:
            super().handle_message(source, message)

        if message.type == MessageTypes.RIB_QUERY_NEXT_HOP:
            destination = message.content
            next_hop, distance = self.rib_query_next_hop(source, destination)
            return (next_hop, distance)

        elif message.type == MessageTypes.RIB_QUERY_NEXT_MULTICAST_HOPS:
            multicast_group = message.content
            next_hops = self.rib_query_next_multicast_hops(source, multicast_group)
            return next_hops

        elif message.type == MessageTypes.RIB_ADD_LINK:
            (node1, node2, link_cost) = message.content
            self.rib_add_link(node1, node2, link_cost)

        elif message.type == MessageTypes.RIB_ADD_OWNERSHIP:
            (router, node) = message.content
            self.rib_add_ownership(router, node)

        elif message.type == MessageTypes.MULTICAST_CREATE_GROUP:
            group_name = message.content
            self.rib_create_multicast_group(source, group_name)

        elif message.type == MessageTypes.MULTICAST_JOIN_GROUP:
            group_name = message.content
            self.rib_join_multicast_group(source, group_name)

    # Dijkstra's algorithm for finding next hop (thanks, ChatGPT)
    def rib_query_next_hop(self, start, destination):
        # Initialize distance and previous node dictionaries
        distances = {node: float("infinity") for node in self.rib_nodes}
        previous_nodes = {node: None for node in self.rib_nodes}

        # Initialize the priority list
        queue = [(0, start)]
        distances[start] = 0

        while queue:
            # Find and remove the node with the smallest distance
            current_distance, current_node = min(queue, key=lambda x: x[0])
            queue.remove((current_distance, current_node))

            # If destination is reached, backtrack to find the first hop
            if current_node == destination:
                first_hop = backtrack_first_hop(start, destination, previous_nodes)
                return first_hop, distances[destination]

            # Iterate over neighbors of the current node
            for edge in self.rib_edges:
                if current_node in edge:
                    neighbor = edge[0] if current_node == edge[1] else edge[1]
                    length = edge[2]
                    new_distance = current_distance + length

                    # Update the distance if a shorter path is found
                    if new_distance < distances[neighbor]:
                        distances[neighbor] = new_distance
                        previous_nodes[neighbor] = current_node
                        queue.append((new_distance, neighbor))

        # Check if the destination is owned by a child router
        for router, nodes in self.rib_child_router_ownerships.items():
            if destination in nodes:
                return self.rib_query_next_hop(start, router)

        # Send to parent router instead if no path is found
        if self.parent_router:
            return self.get_next_hop(self.parent_router)

        return []  # Path not found

    def rib_query_next_multicast_hops(self, start, multicast_group_name):
        if not multicast_group_name in self.rib_multicast_groups:
            print(f"[{self}] Could not find multicast group '{multicast_group_name}'!")
            return

        # if not start in self.rib_multicast_groups[multicast_group_name]["nodes"]:
        #     print(f"[{self}] {start} not in multicast group '{multicast_group_name}'!")
        #     return

        multicast_group = self.rib_multicast_groups[multicast_group_name]

        next_hops = [
            n2 if n1 == start else n1
            for n1, n2, _ in multicast_group["edges"]
            if start in (n1, n2)
        ]

        # If the node is a router, also check the parent RIB for potenital links outside the domain
        if start == self and self.parent_router:
            message = Message(
                content=multicast_group_name,
                type=MessageTypes.RIB_QUERY_NEXT_MULTICAST_HOPS,
            )
            external_next_hops = self.send_message(self, self.parent_router, message)
            next_hops.extend(external_next_hops)

        return next_hops

    # Returns the full shortest path (a list of edges) from 'start' to any of the nodes in 'destinations'
    def rib_query_join_multicast_group_path(self, start, destinations):
        # Initialize distance and previous node dictionaries
        distances = {node: float("infinity") for node in self.rib_nodes}
        previous_nodes = {node: None for node in self.rib_nodes}

        # Initialize the priority list
        queue = [(0, start)]
        distances[start] = 0

        while queue:
            # Find and remove the node with the smallest distance
            current_distance, current_node = min(queue, key=lambda x: x[0])
            queue.remove((current_distance, current_node))

            # If a destination is reached, backtrack to find the full path as edges
            if current_node in destinations:
                return backtrack_full_path(
                    start, current_node, previous_nodes, self.rib_edges
                )

            # Iterate over neighbors of the current node
            for edge in self.rib_edges:
                if current_node in edge:
                    neighbor = edge[0] if current_node == edge[1] else edge[1]
                    length = edge[2]
                    new_distance = current_distance + length

                    # Update the distance if a shorter path is found
                    if new_distance < distances[neighbor]:
                        distances[neighbor] = new_distance
                        previous_nodes[neighbor] = current_node
                        queue.append((new_distance, neighbor))

        return None  # Path not found to any destination

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

    def rib_create_multicast_group(self, creator, group_name):
        self.rib_multicast_groups[group_name] = {
            "members": set([creator]),
            "nodes": set([creator]),
            "edges": set(),
        }

        # Propagate group creation up the tree
        if self.parent_router:
            message = Message(
                content=group_name, type=MessageTypes.MULTICAST_CREATE_GROUP
            )
            self.send_message(self, self.parent_router, message)

    def rib_join_multicast_group(self, node, group_name):
        # If this RIB doesn't know about the multicast group, forward to parent router
        if not group_name in self.rib_multicast_groups:
            if not self.parent_router:
                print(f"Could not find multicast group '{group_name}'!")
                return

            message = Message(
                content=group_name, type=MessageTypes.MULTICAST_JOIN_GROUP
            )
            self.send_message(self, self.parent_router, message)

            self.rib_multicast_groups[group_name] = {
                "members": set(),
                "nodes": set(),
                "edges": set(),
            }

            # Router adds itself to the multicast tree
            self.rib_multicast_groups[group_name]["nodes"].add(self)

        if self.rib_multicast_groups[group_name]["nodes"]:
            # Find edges that connects the node to the multicast tree
            nodes, edges = self.rib_query_join_multicast_group_path(
                node, self.rib_multicast_groups[group_name]["nodes"]
            )

            # Add nodes and edges to the multicast tree
            self.rib_multicast_groups[group_name]["nodes"].update(nodes)
            self.rib_multicast_groups[group_name]["edges"].update(edges)

        self.rib_multicast_groups[group_name]["nodes"].add(node)
        self.rib_multicast_groups[group_name]["members"].add(node)


# Helper function
def backtrack_first_hop(start, destination, previous_nodes):
    # Backtrack from destination to start, return the first hop
    node = destination
    while previous_nodes[node] != start:
        node = previous_nodes[node]

        # Handle case where no path exists
        if node is None:
            return None

    return node


# Helper function
def backtrack_full_path(start, destination, previous_nodes, edges):
    path_edges = []
    path_nodes = {start, destination}
    node = destination

    while node != start:
        prev_node = previous_nodes[node]
        if prev_node is None:
            return None  # In case the path is broken

        # Add the node to the path nodes set
        path_nodes.add(prev_node)

        # Find the edge that connects the current node and the previous node
        for edge in edges:
            if (prev_node in edge) and (node in edge):
                path_edges.append(edge)
                break

        node = prev_node

    return (
        path_nodes,
        path_edges[::-1],
    )  # Return the path as nodes and edges in the correct order from start to destination


def main():
    # Enable to print every message received at any node. Disable to only print messages received at clients.
    global DEBUG

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
    switch4 = Switch("switch4", parent_router=routerB)
    switch4.add_neighbor(routerB)
    client5 = Client("client5", switch3)
    client6 = Client("client6", switch3)
    client7 = Client("client7", switch4)
    client8 = Client("client8", switch4)

    # Send two cross-domain messages
    # client1.send_message(client1, client8, Message("Hello World!", MessageTypes.PING))
    # client8.send_message(client8, client1, Message("Hello World!", MessageTypes.PING))

    # Multicast example
    client1.create_multicast_group("group1")
    client2.join_multicast_group("group1")
    client4.join_multicast_group("group1")
    client8.join_multicast_group("group1")
    client1.send_multicast_message(
        client1, "group1", Message("Hello from client1!", MessageTypes.PING)
    )
    client8.send_multicast_message(
        client8, "group1", Message("Hello from client8!", MessageTypes.PING)
    )

    print("done")


main()
