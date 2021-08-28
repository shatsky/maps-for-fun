(function (global, factory) {
typeof exports === 'object' && typeof module !== 'undefined' ? module.exports = factory() :
typeof define === 'function' && define.amd ? define(factory) :
(global = typeof globalThis !== 'undefined' ? globalThis : global || self, global.KDBush = factory());
}(this, (function () { 'use strict';

var ARRAY_TYPES = [
    Int8Array, Uint8Array, Uint8ClampedArray, Int16Array, Uint16Array,
    Int32Array, Uint32Array, Float32Array, Float64Array
];

var VERSION = 1; // serialized format version
var HEADER_SIZE = 8;

var KDBush = function KDBush(numItems, nodeSize, ArrayType, data) {
    if ( nodeSize === void 0 ) nodeSize = 64;
    if ( ArrayType === void 0 ) ArrayType = Float64Array;

    if (isNaN(numItems) || numItems <= 0) { throw new Error(("Unpexpected numItems value: " + numItems + ".")); }

    this.numItems = +numItems;
    this.nodeSize = Math.min(Math.max(+nodeSize, 2), 65535);
    this.ArrayType = ArrayType;
    //this.IndexArrayType = numItems < 65536 ? Uint16Array : Uint32Array;
    this.IndexArrayType = Int32Array;

    var arrayTypeIndex = ARRAY_TYPES.indexOf(this.ArrayType);
    var coordsByteSize = numItems * 2 * this.ArrayType.BYTES_PER_ELEMENT;
    var idsByteSize = numItems * this.IndexArrayType.BYTES_PER_ELEMENT;
    var padCoords = (8 - idsByteSize % 8) % 8;

    if (arrayTypeIndex < 0) {
        throw new Error(("Unexpected typed array class: " + ArrayType + "."));
    }

    if (data && (data instanceof ArrayBuffer)) { // reconstruct an index from a buffer
        this.data = data;
        console.log('ids offset and len', HEADER_SIZE, numItems)
        this.ids = new this.IndexArrayType(this.data, HEADER_SIZE, numItems);
        console.log('coords offset and len', HEADER_SIZE + idsByteSize + padCoords, numItems * 2)
        this.coords = new this.ArrayType(this.data, HEADER_SIZE + idsByteSize + padCoords, numItems * 2);
        this._pos = numItems * 2;
        this._finished = true;
    } else { // initialize a new index
        this.data = new ArrayBuffer(HEADER_SIZE + coordsByteSize + idsByteSize + padCoords);
        console.log('ids offset and len', HEADER_SIZE, numItems)
        this.ids = new this.IndexArrayType(this.data, HEADER_SIZE, numItems);
        console.log('coords offset and len', HEADER_SIZE + idsByteSize + padCoords, numItems * 2)
        this.coords = new this.ArrayType(this.data, HEADER_SIZE + idsByteSize + padCoords, numItems * 2);
        this._pos = 0;
        this._finished = false;

        // set header
        new Uint8Array(this.data, 0, 2).set([0xdb, (VERSION << 4) + arrayTypeIndex]);
        new Uint16Array(this.data, 2, 1)[0] = nodeSize;
        new Uint32Array(this.data, 4, 1)[0] = numItems;
    }
};

KDBush.from = function from (data) {
    if (!(data instanceof ArrayBuffer)) {
        throw new Error('Data must be an instance of ArrayBuffer.');
    }
    var ref = new Uint8Array(data, 0, 2);
        var magic = ref[0];
        var versionAndType = ref[1];
    if (magic !== 0xdb) {
        throw new Error('Data does not appear to be in a KDBush format.');
    }
    if (versionAndType >> 4 !== VERSION) {
        throw new Error(("Got v" + (versionAndType >> 4) + " data when expected v" + VERSION + "."));
    }
    var ref$1 = new Uint16Array(data, 2, 1);
        var nodeSize = ref$1[0];
    var ref$2 = new Uint32Array(data, 4, 1);
        var numItems = ref$2[0];

    return new KDBush(numItems, nodeSize, ARRAY_TYPES[versionAndType & 0x0f], data);
};

//KDBush.prototype.add = function add (x, y) {
KDBush.prototype.add = function add (x, y, id) {
    var index = this._pos >> 1;
    //this.ids[index] = index;
    this.ids[index] = id;
    this.coords[this._pos++] = x;
    this.coords[this._pos++] = y;
    return index;
};

KDBush.prototype.finish = function finish () {
    var numAdded = this._pos >> 1;
    if (numAdded !== this.numItems) {
        throw new Error(("Added " + numAdded + " items when expected " + (this.numItems) + "."));
    }
    // kd-sort both arrays for efficient search
    sort(this.ids, this.coords, this.nodeSize, 0, this.numItems - 1, 0);

    this._finished = true;
    return this;
};

KDBush.prototype.range = function range (minX, minY, maxX, maxY) {
    if (!this._finished) { throw new Error('Data not yet indexed - call index.finish().'); }

    var ref = this;
        var ids = ref.ids;
        var coords = ref.coords;
        var nodeSize = ref.nodeSize;
    var stack = [0, ids.length - 1, 0];
    var result = [];

    // recursively search for items in range in the kd-sorted arrays
    while (stack.length) {
        var axis = stack.pop();
        var right = stack.pop();
        var left = stack.pop();

        // if we reached "tree node", search linearly
        if (right - left <= nodeSize) {
            for (var i = left; i <= right; i++) {
                var x = coords[2 * i];
                var y = coords[2 * i + 1];
                if (x >= minX && x <= maxX && y >= minY && y <= maxY) { result.push(ids[i]); }
            }
            continue;
        }

        // otherwise find the middle index
        var m = (left + right) >> 1;

        // include the middle item if it's in range
        var x$1 = coords[2 * m];
        var y$1 = coords[2 * m + 1];
        if (x$1 >= minX && x$1 <= maxX && y$1 >= minY && y$1 <= maxY) { result.push(ids[m]); }

        // queue search in halves that intersect the query
        if (axis === 0 ? minX <= x$1 : minY <= y$1) {
            stack.push(left);
            stack.push(m - 1);
            stack.push(1 - axis);
        }
        if (axis === 0 ? maxX >= x$1 : maxY >= y$1) {
            stack.push(m + 1);
            stack.push(right);
            stack.push(1 - axis);
        }
    }

    return result;
};

KDBush.prototype.within = function within (qx, qy, r) {
    if (!this._finished) { throw new Error('Data not yet indexed - call index.finish().'); }

    var ref = this;
        var ids = ref.ids;
        var coords = ref.coords;
        var nodeSize = ref.nodeSize;
    var stack = [0, ids.length - 1, 0];
    var result = [];
    var r2 = r * r;

    // recursively search for items within radius in the kd-sorted arrays
    while (stack.length) {
        var axis = stack.pop();
        var right = stack.pop();
        var left = stack.pop();

        // if we reached "tree node", search linearly
        if (right - left <= nodeSize) {
            for (var i = left; i <= right; i++) {
                if (sqDist(coords[2 * i], coords[2 * i + 1], qx, qy) <= r2) { result.push(ids[i]); }
            }
            continue;
        }

        // otherwise find the middle index
        var m = (left + right) >> 1;

        // include the middle item if it's in range
        var x = coords[2 * m];
        var y = coords[2 * m + 1];
        if (sqDist(x, y, qx, qy) <= r2) { result.push(ids[m]); }

        // queue search in halves that intersect the query
        if (axis === 0 ? qx - r <= x : qy - r <= y) {
            stack.push(left);
            stack.push(m - 1);
            stack.push(1 - axis);
        }
        if (axis === 0 ? qx + r >= x : qy + r >= y) {
            stack.push(m + 1);
            stack.push(right);
            stack.push(1 - axis);
        }
    }

    return result;
};

function sort(ids, coords, nodeSize, left, right, axis) {
    if (right - left <= nodeSize) { return; }

    var m = (left + right) >> 1; // middle index

    // sort ids and coords around the middle index so that the halves lie
    // either left/right or top/bottom correspondingly (taking turns)
    select(ids, coords, m, left, right, axis);

    // recursively kd-sort first half and second half on the opposite axis
    sort(ids, coords, nodeSize, left, m - 1, 1 - axis);
    sort(ids, coords, nodeSize, m + 1, right, 1 - axis);
}

// custom Floyd-Rivest selection algorithm: sort ids and coords so that
// [left..k-1] items are smaller than k-th item (on either x or y axis)
function select(ids, coords, k, left, right, axis) {

    while (right > left) {
        if (right - left > 600) {
            var n = right - left + 1;
            var m = k - left + 1;
            var z = Math.log(n);
            var s = 0.5 * Math.exp(2 * z / 3);
            var sd = 0.5 * Math.sqrt(z * s * (n - s) / n) * (m - n / 2 < 0 ? -1 : 1);
            var newLeft = Math.max(left, Math.floor(k - m * s / n + sd));
            var newRight = Math.min(right, Math.floor(k + (n - m) * s / n + sd));
            select(ids, coords, k, newLeft, newRight, axis);
        }

        var t = coords[2 * k + axis];
        var i = left;
        var j = right;

        swapItem(ids, coords, left, k);
        if (coords[2 * right + axis] > t) { swapItem(ids, coords, left, right); }

        while (i < j) {
            swapItem(ids, coords, i, j);
            i++;
            j--;
            while (coords[2 * i + axis] < t) { i++; }
            while (coords[2 * j + axis] > t) { j--; }
        }

        if (coords[2 * left + axis] === t) { swapItem(ids, coords, left, j); }
        else {
            j++;
            swapItem(ids, coords, j, right);
        }

        if (j <= k) { left = j + 1; }
        if (k <= j) { right = j - 1; }
    }
}

function swapItem(ids, coords, i, j) {
    swap(ids, i, j);
    swap(coords, 2 * i, 2 * j);
    swap(coords, 2 * i + 1, 2 * j + 1);
}

function swap(arr, i, j) {
    var tmp = arr[i];
    arr[i] = arr[j];
    arr[j] = tmp;
}

function sqDist(ax, ay, bx, by) {
    var dx = ax - bx;
    var dy = ay - by;
    return dx * dx + dy * dy;
}

return KDBush;

})));
