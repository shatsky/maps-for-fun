import math


def compareMax(a, b):
    return b.max - a.max;


class Queue:
    items = []

    #!!!
    # insert before 1st item that's < one being inserted
    def push(self, item):
        for idx in range(len(self.items)):
            if self.items[idx].max < item.max:
                self.items.insert(idx, item)
                return
        self.items.append(item)

    def pop(self):
        return self.items.pop(0)

    def __len__(self):
        return len(self.items)


def polylabel(polygon, precision, debug=True):
    precision = precision or 1.0;

    # find the bounding box of the outer ring
    minX, minY, maxX, maxY = None, None, None, None;
    for i in range(0, len(polygon[0])):
        p = polygon[0][i];
        if not i or p[0] < minX: minX = p[0];
        if not i or p[1] < minY: minY = p[1];
        if not i or p[0] > maxX: maxX = p[0];
        if not i or p[1] > maxY: maxY = p[1];

    width = maxX - minX;
    height = maxY - minY;
    cellSize = min(width, height);
    h = cellSize / 2;

    if cellSize == 0:
        degeneratePoleOfInaccessibility_xy = [minX, minY];
        degeneratePoleOfInaccessibility_distance = 0;
        return degeneratePoleOfInaccessibility_xy, degeneratePoleOfInaccessibility_distance;

    # a priority queue of cells in order of their "potential" (max distance to polygon)
    cellQueue = Queue();

    # cover polygon with initial cells
    for x in range(minX, maxX, cellSize):
        for y in range(minY, maxY, cellSize):
            cellQueue.push(Cell(x + h, y + h, h, polygon));

    # take centroid as the first best guess
    bestCell = getCentroidCell(polygon);

    # second guess: bounding box centroid
    bboxCell = Cell(minX + width / 2, minY + height / 2, 0, polygon);
    if bboxCell.d > bestCell.d: bestCell = bboxCell;

    numProbes = len(cellQueue);

    while len(cellQueue):
        # pick the most promising cell from the queue
        cell = cellQueue.pop();

        # update the best cell if we found a better one
        if cell.d > bestCell.d:
            bestCell = cell;
            #!!!
            if debug:
                print('found best {0} after {1} probes'.format(round(1e4 * cell.d) / 1e4, numProbes));

        # do not drill down further if there's no chance of a better solution
        if cell.max - bestCell.d <= precision: continue;

        # split the cell into four cells
        h = cell.h / 2;
        cellQueue.push(Cell(cell.x - h, cell.y - h, h, polygon));
        cellQueue.push(Cell(cell.x + h, cell.y - h, h, polygon));
        cellQueue.push(Cell(cell.x - h, cell.y + h, h, polygon));
        cellQueue.push(Cell(cell.x + h, cell.y + h, h, polygon));
        numProbes += 4;

    if debug:
        print('num probes: ' + str(numProbes));
        print('best distance: ' + str(bestCell.d));

    poleOfInaccessibility_xy = [bestCell.x, bestCell.y];
    poleOfInaccessibility_distance = bestCell.d;
    return poleOfInaccessibility_xy, poleOfInaccessibility_distance;

def compareMax(a, b):
    return b.max - a.max;


class Cell:
    def __init__(self, x, y, h, polygon):
        self.x = x; # cell center x
        self.y = y; # cell center y
        self.h = h; # half the cell size
        self.d = pointToPolygonDist(x, y, polygon); # distance from cell center to polygon
        #!!!
        self.max = self.d + self.h * 2**(1/2); # max distance to polygon within a cell


# signed distance from point to polygon outline (negative if point is outside)
def pointToPolygonDist(x, y, polygon):
    inside = False;
    minDistSq = math.inf;

    for k in range(0, len(polygon)):
        ring = polygon[k];

        #!!!
        i = 0
        j = len(ring) - 1
        while i < len(ring):
            a = ring[i];
            b = ring[j];

            #!!!
            if ((a[1] > y) != (b[1] > y)) and\
                (((b[1] - a[1]) != 0 and (x < (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0])) or ((b[1] - a[1]) == 0 and (b[0] - a[0]) * (y - a[1]) > 0)): inside = not inside;

            #!!!
            minDistSq = min(minDistSq, getSegDistSq(x, y, a, b));

            j = i
            i += 1

    #!!!
    return 0 if minDistSq == 0 else (1 if inside else -1) * (minDistSq)**(1/2);

# get polygon centroid
def getCentroidCell(polygon):
    area = 0;
    x = 0;
    y = 0;
    points = polygon[0];

    #!!!
    i = 0
    j = len(points) - 1
    while i < len(points):
        a = points[i];
        b = points[j];
        f = a[0] * b[1] - b[0] * a[1];
        x += (a[0] + b[0]) * f;
        y += (a[1] + b[1]) * f;
        area += f * 3;

        j = i
        i += 1
    if (area == 0):
        return Cell(points[0][0], points[0][1], 0, polygon);
    return Cell(x / area, y / area, 0, polygon);

# get squared distance from a point to a segment
def getSegDistSq(px, py, a, b):

    x = a[0];
    y = a[1];
    dx = b[0] - x;
    dy = b[1] - y;

    if dx != 0 or dy != 0:

        t = ((px - x) * dx + (py - y) * dy) / (dx * dx + dy * dy);

        if t > 1:
            x = b[0];
            y = b[1];

        elif t > 0:
            x += dx * t;
            y += dy * t;

    dx = px - x;
    dy = py - y;

    return dx * dx + dy * dy;
