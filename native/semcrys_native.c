#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>

#if defined(_WIN32)
#define SEMCRYS_EXPORT __declspec(dllexport)
#else
#define SEMCRYS_EXPORT __attribute__((visibility("default")))
#endif

#define SEMCRYS_ABI_VERSION 2u
#define SEMCRYS_OK 0
#define SEMCRYS_OUTPUT_TOO_SMALL 1
#define SEMCRYS_RANGE 2
#define SEMCRYS_TRUNCATED 3
#define SEMCRYS_UNSUPPORTED 4
#define SEMCRYS_ALLOCATION 5

typedef struct {
    uint64_t left;
    uint64_t right;
    uint64_t replacement;
    unsigned char used;
} rule_slot;

SEMCRYS_EXPORT uint32_t semcrys_native_abi(void) {
    return SEMCRYS_ABI_VERSION;
}

SEMCRYS_EXPORT int semcrys_pack_u63(
    const uint64_t *values,
    size_t count,
    unsigned char *output,
    size_t output_capacity,
    size_t *output_length
) {
    size_t position = 0;
    size_t index;
    if (output_length == NULL || (count && values == NULL) || (output_capacity && output == NULL)) {
        return SEMCRYS_UNSUPPORTED;
    }
    for (index = 0; index < count; ++index) {
        uint64_t value = values[index];
        if (value >= (UINT64_C(1) << 63)) {
            return SEMCRYS_RANGE;
        }
        do {
            unsigned char byte = (unsigned char)(value & UINT64_C(127));
            value >>= 7;
            if (position >= output_capacity) {
                return SEMCRYS_OUTPUT_TOO_SMALL;
            }
            output[position++] = (unsigned char)(byte | (value ? 128 : 0));
        } while (value);
    }
    *output_length = position;
    return SEMCRYS_OK;
}

SEMCRYS_EXPORT int semcrys_unpack_u63(
    const unsigned char *data,
    size_t data_length,
    uint64_t *output,
    size_t output_capacity,
    size_t *output_count
) {
    size_t position = 0;
    size_t count = 0;
    uint64_t current = 0;
    unsigned int shift = 0;
    if (output_count == NULL || (data_length && data == NULL) || (output_capacity && output == NULL)) {
        return SEMCRYS_UNSUPPORTED;
    }
    while (position < data_length) {
        unsigned char byte = data[position++];
        if (shift == 63 && byte > 1) {
            return SEMCRYS_UNSUPPORTED;
        }
        current |= ((uint64_t)(byte & 127)) << shift;
        if (byte < 128) {
            if (count >= output_capacity) {
                return SEMCRYS_OUTPUT_TOO_SMALL;
            }
            output[count++] = current;
            current = 0;
            shift = 0;
        } else {
            shift += 7;
            if (shift > 63) {
                return SEMCRYS_RANGE;
            }
        }
    }
    if (shift != 0) {
        return SEMCRYS_TRUNCATED;
    }
    *output_count = count;
    return SEMCRYS_OK;
}

static int read_canonical_u63(
    const unsigned char *data,
    size_t data_length,
    size_t *position,
    uint64_t *value
) {
    uint64_t current = 0;
    unsigned int shift = 0;
    unsigned char byte;
    if (data == NULL || position == NULL || value == NULL) {
        return SEMCRYS_UNSUPPORTED;
    }
    for (;;) {
        if (*position >= data_length) {
            return SEMCRYS_TRUNCATED;
        }
        byte = data[(*position)++];
        if (shift == 63 && byte > 1) {
            return SEMCRYS_RANGE;
        }
        current |= ((uint64_t)(byte & 127)) << shift;
        if (byte < 128) {
            if (shift && byte == 0) {
                return SEMCRYS_UNSUPPORTED;
            }
            *value = current;
            return SEMCRYS_OK;
        }
        shift += 7;
        if (shift > 63) {
            return SEMCRYS_RANGE;
        }
    }
}

SEMCRYS_EXPORT int semcrys_parse_packed_events(
    const unsigned char *data,
    size_t data_length,
    uint64_t *values,
    uint64_t *lengths,
    size_t output_capacity,
    size_t *output_count
) {
    size_t position = 0;
    size_t count = 0;
    int count_only = values == NULL && lengths == NULL && output_capacity == 0;
    if (output_count == NULL || (data_length && data == NULL) ||
        (!count_only && (values == NULL || lengths == NULL))) {
        return SEMCRYS_UNSUPPORTED;
    }
    while (position < data_length) {
        uint64_t identifier;
        int result = read_canonical_u63(data, data_length, &position, &identifier);
        if (result != SEMCRYS_OK) {
            return result;
        }
        if (!count_only && count >= output_capacity) {
            return SEMCRYS_OUTPUT_TOO_SMALL;
        }
        if (identifier != 0) {
            if (!count_only) {
                values[count] = identifier;
                lengths[count] = 0;
            }
        } else {
            uint64_t literal_length;
            result = read_canonical_u63(data, data_length, &position, &literal_length);
            if (result != SEMCRYS_OK) {
                return result;
            }
            if (literal_length == 0 || literal_length > (uint64_t)(data_length - position)) {
                return literal_length == 0 ? SEMCRYS_UNSUPPORTED : SEMCRYS_TRUNCATED;
            }
            if (!count_only) {
                values[count] = (uint64_t)position;
                lengths[count] = literal_length;
            }
            position += (size_t)literal_length;
        }
        ++count;
    }
    *output_count = count;
    return SEMCRYS_OK;
}

static uint64_t mix64(uint64_t value) {
    value ^= value >> 30;
    value *= UINT64_C(0xbf58476d1ce4e5b9);
    value ^= value >> 27;
    value *= UINT64_C(0x94d049bb133111eb);
    return value ^ (value >> 31);
}

static size_t pair_hash(uint64_t left, uint64_t right, size_t mask) {
    return (size_t)(mix64(left ^ (mix64(right) + UINT64_C(0x9e3779b97f4a7c15))) & mask);
}

static int insert_rule(rule_slot *table, size_t mask, uint64_t left, uint64_t right, uint64_t replacement) {
    size_t slot = pair_hash(left, right, mask);
    size_t start = slot;
    do {
        if (!table[slot].used || (table[slot].left == left && table[slot].right == right)) {
            table[slot].left = left;
            table[slot].right = right;
            table[slot].replacement = replacement;
            table[slot].used = 1;
            return SEMCRYS_OK;
        }
        slot = (slot + 1) & mask;
    } while (slot != start);
    return SEMCRYS_ALLOCATION;
}

static int lookup_rule(const rule_slot *table, size_t mask, uint64_t left, uint64_t right, uint64_t *replacement) {
    size_t slot = pair_hash(left, right, mask);
    size_t start = slot;
    do {
        if (!table[slot].used) {
            return 0;
        }
        if (table[slot].left == left && table[slot].right == right) {
            *replacement = table[slot].replacement;
            return 1;
        }
        slot = (slot + 1) & mask;
    } while (slot != start);
    return 0;
}

SEMCRYS_EXPORT int semcrys_fold_pairs(
    const uint64_t *events,
    size_t event_count,
    const uint64_t *left,
    const uint64_t *right,
    const uint64_t *replacement,
    size_t rule_count,
    uint64_t *output,
    size_t output_capacity,
    size_t *output_count
) {
    uint64_t *current = NULL;
    uint64_t *next = NULL;
    rule_slot *table = NULL;
    size_t table_size = 1;
    size_t table_mask;
    size_t current_count = event_count;
    size_t index;
    int result = SEMCRYS_OK;

    if (output_count == NULL || output_capacity < event_count ||
        (event_count && (events == NULL || output == NULL)) ||
        (rule_count && (left == NULL || right == NULL || replacement == NULL))) {
        return SEMCRYS_OUTPUT_TOO_SMALL;
    }
    if (!rule_count || !event_count) {
        if (event_count) {
            memcpy(output, events, event_count * sizeof(uint64_t));
        }
        *output_count = event_count;
        return SEMCRYS_OK;
    }
    if (event_count > SIZE_MAX / sizeof(uint64_t)) {
        return SEMCRYS_ALLOCATION;
    }
    if (rule_count > SIZE_MAX / 2) {
        return SEMCRYS_ALLOCATION;
    }
    while (table_size < rule_count * 2) {
        if (table_size > SIZE_MAX / 2) {
            return SEMCRYS_ALLOCATION;
        }
        table_size <<= 1;
    }
    table_mask = table_size - 1;
    table = (rule_slot *)calloc(table_size, sizeof(rule_slot));
    current = (uint64_t *)malloc(event_count * sizeof(uint64_t));
    next = (uint64_t *)malloc(event_count * sizeof(uint64_t));
    if (table == NULL || current == NULL || next == NULL) {
        result = SEMCRYS_ALLOCATION;
        goto cleanup;
    }
    memcpy(current, events, event_count * sizeof(uint64_t));
    for (index = 0; index < rule_count; ++index) {
        result = insert_rule(table, table_mask, left[index], right[index], replacement[index]);
        if (result != SEMCRYS_OK) {
            goto cleanup;
        }
    }
    for (;;) {
        size_t source = 0;
        size_t target = 0;
        int changed = 0;
        while (source < current_count) {
            uint64_t folded;
            if (source + 1 < current_count && lookup_rule(table, table_mask, current[source], current[source + 1], &folded)) {
                next[target++] = folded;
                source += 2;
                changed = 1;
            } else {
                next[target++] = current[source++];
            }
        }
        {
            uint64_t *swap = current;
            current = next;
            next = swap;
        }
        current_count = target;
        if (!changed) {
            break;
        }
    }
    memcpy(output, current, current_count * sizeof(uint64_t));
    *output_count = current_count;

cleanup:
    free(table);
    free(current);
    free(next);
    return result;
}
