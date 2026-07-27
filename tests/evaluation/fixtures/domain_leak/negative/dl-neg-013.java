import org.springframework.web.bind.annotation.*;
import java.time.Instant;
import java.util.*;

/**
 * Large DTO controller — clean public contract with no internal entity exposure.
 * Generated to exercise the large-patch evaluation path (20+ KiB).
 */
@RestController
class LargeDataController {

    @GetMapping("/data/0")
    public DataResponse0 getData0(@RequestParam(required = false) String filter) {
        var record = new DataResponse0(
            UUID.randomUUID().toString(),
            "item-0",
            Instant.now(),
            0,
            "category-0",
            "description for record 0"
        );
        return record;
    }

record DataResponse0(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/1")
    public DataResponse1 getData1(@RequestParam(required = false) String filter) {
        var record = new DataResponse1(
            UUID.randomUUID().toString(),
            "item-1",
            Instant.now(),
            1,
            "category-1",
            "description for record 1"
        );
        return record;
    }

record DataResponse1(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/2")
    public DataResponse2 getData2(@RequestParam(required = false) String filter) {
        var record = new DataResponse2(
            UUID.randomUUID().toString(),
            "item-2",
            Instant.now(),
            2,
            "category-2",
            "description for record 2"
        );
        return record;
    }

record DataResponse2(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/3")
    public DataResponse3 getData3(@RequestParam(required = false) String filter) {
        var record = new DataResponse3(
            UUID.randomUUID().toString(),
            "item-3",
            Instant.now(),
            3,
            "category-3",
            "description for record 3"
        );
        return record;
    }

record DataResponse3(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/4")
    public DataResponse4 getData4(@RequestParam(required = false) String filter) {
        var record = new DataResponse4(
            UUID.randomUUID().toString(),
            "item-4",
            Instant.now(),
            4,
            "category-4",
            "description for record 4"
        );
        return record;
    }

record DataResponse4(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/5")
    public DataResponse5 getData5(@RequestParam(required = false) String filter) {
        var record = new DataResponse5(
            UUID.randomUUID().toString(),
            "item-5",
            Instant.now(),
            5,
            "category-5",
            "description for record 5"
        );
        return record;
    }

record DataResponse5(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/6")
    public DataResponse6 getData6(@RequestParam(required = false) String filter) {
        var record = new DataResponse6(
            UUID.randomUUID().toString(),
            "item-6",
            Instant.now(),
            6,
            "category-6",
            "description for record 6"
        );
        return record;
    }

record DataResponse6(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/7")
    public DataResponse7 getData7(@RequestParam(required = false) String filter) {
        var record = new DataResponse7(
            UUID.randomUUID().toString(),
            "item-7",
            Instant.now(),
            7,
            "category-7",
            "description for record 7"
        );
        return record;
    }

record DataResponse7(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/8")
    public DataResponse8 getData8(@RequestParam(required = false) String filter) {
        var record = new DataResponse8(
            UUID.randomUUID().toString(),
            "item-8",
            Instant.now(),
            8,
            "category-8",
            "description for record 8"
        );
        return record;
    }

record DataResponse8(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/9")
    public DataResponse9 getData9(@RequestParam(required = false) String filter) {
        var record = new DataResponse9(
            UUID.randomUUID().toString(),
            "item-9",
            Instant.now(),
            9,
            "category-9",
            "description for record 9"
        );
        return record;
    }

record DataResponse9(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/10")
    public DataResponse10 getData10(@RequestParam(required = false) String filter) {
        var record = new DataResponse10(
            UUID.randomUUID().toString(),
            "item-10",
            Instant.now(),
            10,
            "category-0",
            "description for record 10"
        );
        return record;
    }

record DataResponse10(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/11")
    public DataResponse11 getData11(@RequestParam(required = false) String filter) {
        var record = new DataResponse11(
            UUID.randomUUID().toString(),
            "item-11",
            Instant.now(),
            11,
            "category-1",
            "description for record 11"
        );
        return record;
    }

record DataResponse11(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/12")
    public DataResponse12 getData12(@RequestParam(required = false) String filter) {
        var record = new DataResponse12(
            UUID.randomUUID().toString(),
            "item-12",
            Instant.now(),
            12,
            "category-2",
            "description for record 12"
        );
        return record;
    }

record DataResponse12(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/13")
    public DataResponse13 getData13(@RequestParam(required = false) String filter) {
        var record = new DataResponse13(
            UUID.randomUUID().toString(),
            "item-13",
            Instant.now(),
            13,
            "category-3",
            "description for record 13"
        );
        return record;
    }

record DataResponse13(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/14")
    public DataResponse14 getData14(@RequestParam(required = false) String filter) {
        var record = new DataResponse14(
            UUID.randomUUID().toString(),
            "item-14",
            Instant.now(),
            14,
            "category-4",
            "description for record 14"
        );
        return record;
    }

record DataResponse14(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/15")
    public DataResponse15 getData15(@RequestParam(required = false) String filter) {
        var record = new DataResponse15(
            UUID.randomUUID().toString(),
            "item-15",
            Instant.now(),
            15,
            "category-5",
            "description for record 15"
        );
        return record;
    }

record DataResponse15(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/16")
    public DataResponse16 getData16(@RequestParam(required = false) String filter) {
        var record = new DataResponse16(
            UUID.randomUUID().toString(),
            "item-16",
            Instant.now(),
            16,
            "category-6",
            "description for record 16"
        );
        return record;
    }

record DataResponse16(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/17")
    public DataResponse17 getData17(@RequestParam(required = false) String filter) {
        var record = new DataResponse17(
            UUID.randomUUID().toString(),
            "item-17",
            Instant.now(),
            17,
            "category-7",
            "description for record 17"
        );
        return record;
    }

record DataResponse17(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/18")
    public DataResponse18 getData18(@RequestParam(required = false) String filter) {
        var record = new DataResponse18(
            UUID.randomUUID().toString(),
            "item-18",
            Instant.now(),
            18,
            "category-8",
            "description for record 18"
        );
        return record;
    }

record DataResponse18(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/19")
    public DataResponse19 getData19(@RequestParam(required = false) String filter) {
        var record = new DataResponse19(
            UUID.randomUUID().toString(),
            "item-19",
            Instant.now(),
            19,
            "category-9",
            "description for record 19"
        );
        return record;
    }

record DataResponse19(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/20")
    public DataResponse20 getData20(@RequestParam(required = false) String filter) {
        var record = new DataResponse20(
            UUID.randomUUID().toString(),
            "item-20",
            Instant.now(),
            20,
            "category-0",
            "description for record 20"
        );
        return record;
    }

record DataResponse20(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/21")
    public DataResponse21 getData21(@RequestParam(required = false) String filter) {
        var record = new DataResponse21(
            UUID.randomUUID().toString(),
            "item-21",
            Instant.now(),
            21,
            "category-1",
            "description for record 21"
        );
        return record;
    }

record DataResponse21(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/22")
    public DataResponse22 getData22(@RequestParam(required = false) String filter) {
        var record = new DataResponse22(
            UUID.randomUUID().toString(),
            "item-22",
            Instant.now(),
            22,
            "category-2",
            "description for record 22"
        );
        return record;
    }

record DataResponse22(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/23")
    public DataResponse23 getData23(@RequestParam(required = false) String filter) {
        var record = new DataResponse23(
            UUID.randomUUID().toString(),
            "item-23",
            Instant.now(),
            23,
            "category-3",
            "description for record 23"
        );
        return record;
    }

record DataResponse23(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/24")
    public DataResponse24 getData24(@RequestParam(required = false) String filter) {
        var record = new DataResponse24(
            UUID.randomUUID().toString(),
            "item-24",
            Instant.now(),
            24,
            "category-4",
            "description for record 24"
        );
        return record;
    }

record DataResponse24(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/25")
    public DataResponse25 getData25(@RequestParam(required = false) String filter) {
        var record = new DataResponse25(
            UUID.randomUUID().toString(),
            "item-25",
            Instant.now(),
            25,
            "category-5",
            "description for record 25"
        );
        return record;
    }

record DataResponse25(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/26")
    public DataResponse26 getData26(@RequestParam(required = false) String filter) {
        var record = new DataResponse26(
            UUID.randomUUID().toString(),
            "item-26",
            Instant.now(),
            26,
            "category-6",
            "description for record 26"
        );
        return record;
    }

record DataResponse26(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/27")
    public DataResponse27 getData27(@RequestParam(required = false) String filter) {
        var record = new DataResponse27(
            UUID.randomUUID().toString(),
            "item-27",
            Instant.now(),
            27,
            "category-7",
            "description for record 27"
        );
        return record;
    }

record DataResponse27(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/28")
    public DataResponse28 getData28(@RequestParam(required = false) String filter) {
        var record = new DataResponse28(
            UUID.randomUUID().toString(),
            "item-28",
            Instant.now(),
            28,
            "category-8",
            "description for record 28"
        );
        return record;
    }

record DataResponse28(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/29")
    public DataResponse29 getData29(@RequestParam(required = false) String filter) {
        var record = new DataResponse29(
            UUID.randomUUID().toString(),
            "item-29",
            Instant.now(),
            29,
            "category-9",
            "description for record 29"
        );
        return record;
    }

record DataResponse29(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/30")
    public DataResponse30 getData30(@RequestParam(required = false) String filter) {
        var record = new DataResponse30(
            UUID.randomUUID().toString(),
            "item-30",
            Instant.now(),
            30,
            "category-0",
            "description for record 30"
        );
        return record;
    }

record DataResponse30(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/31")
    public DataResponse31 getData31(@RequestParam(required = false) String filter) {
        var record = new DataResponse31(
            UUID.randomUUID().toString(),
            "item-31",
            Instant.now(),
            31,
            "category-1",
            "description for record 31"
        );
        return record;
    }

record DataResponse31(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/32")
    public DataResponse32 getData32(@RequestParam(required = false) String filter) {
        var record = new DataResponse32(
            UUID.randomUUID().toString(),
            "item-32",
            Instant.now(),
            32,
            "category-2",
            "description for record 32"
        );
        return record;
    }

record DataResponse32(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/33")
    public DataResponse33 getData33(@RequestParam(required = false) String filter) {
        var record = new DataResponse33(
            UUID.randomUUID().toString(),
            "item-33",
            Instant.now(),
            33,
            "category-3",
            "description for record 33"
        );
        return record;
    }

record DataResponse33(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/34")
    public DataResponse34 getData34(@RequestParam(required = false) String filter) {
        var record = new DataResponse34(
            UUID.randomUUID().toString(),
            "item-34",
            Instant.now(),
            34,
            "category-4",
            "description for record 34"
        );
        return record;
    }

record DataResponse34(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/35")
    public DataResponse35 getData35(@RequestParam(required = false) String filter) {
        var record = new DataResponse35(
            UUID.randomUUID().toString(),
            "item-35",
            Instant.now(),
            35,
            "category-5",
            "description for record 35"
        );
        return record;
    }

record DataResponse35(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/36")
    public DataResponse36 getData36(@RequestParam(required = false) String filter) {
        var record = new DataResponse36(
            UUID.randomUUID().toString(),
            "item-36",
            Instant.now(),
            36,
            "category-6",
            "description for record 36"
        );
        return record;
    }

record DataResponse36(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/37")
    public DataResponse37 getData37(@RequestParam(required = false) String filter) {
        var record = new DataResponse37(
            UUID.randomUUID().toString(),
            "item-37",
            Instant.now(),
            37,
            "category-7",
            "description for record 37"
        );
        return record;
    }

record DataResponse37(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/38")
    public DataResponse38 getData38(@RequestParam(required = false) String filter) {
        var record = new DataResponse38(
            UUID.randomUUID().toString(),
            "item-38",
            Instant.now(),
            38,
            "category-8",
            "description for record 38"
        );
        return record;
    }

record DataResponse38(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/39")
    public DataResponse39 getData39(@RequestParam(required = false) String filter) {
        var record = new DataResponse39(
            UUID.randomUUID().toString(),
            "item-39",
            Instant.now(),
            39,
            "category-9",
            "description for record 39"
        );
        return record;
    }

record DataResponse39(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/40")
    public DataResponse40 getData40(@RequestParam(required = false) String filter) {
        var record = new DataResponse40(
            UUID.randomUUID().toString(),
            "item-40",
            Instant.now(),
            40,
            "category-0",
            "description for record 40"
        );
        return record;
    }

record DataResponse40(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/41")
    public DataResponse41 getData41(@RequestParam(required = false) String filter) {
        var record = new DataResponse41(
            UUID.randomUUID().toString(),
            "item-41",
            Instant.now(),
            41,
            "category-1",
            "description for record 41"
        );
        return record;
    }

record DataResponse41(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/42")
    public DataResponse42 getData42(@RequestParam(required = false) String filter) {
        var record = new DataResponse42(
            UUID.randomUUID().toString(),
            "item-42",
            Instant.now(),
            42,
            "category-2",
            "description for record 42"
        );
        return record;
    }

record DataResponse42(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/43")
    public DataResponse43 getData43(@RequestParam(required = false) String filter) {
        var record = new DataResponse43(
            UUID.randomUUID().toString(),
            "item-43",
            Instant.now(),
            43,
            "category-3",
            "description for record 43"
        );
        return record;
    }

record DataResponse43(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/44")
    public DataResponse44 getData44(@RequestParam(required = false) String filter) {
        var record = new DataResponse44(
            UUID.randomUUID().toString(),
            "item-44",
            Instant.now(),
            44,
            "category-4",
            "description for record 44"
        );
        return record;
    }

record DataResponse44(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/45")
    public DataResponse45 getData45(@RequestParam(required = false) String filter) {
        var record = new DataResponse45(
            UUID.randomUUID().toString(),
            "item-45",
            Instant.now(),
            45,
            "category-5",
            "description for record 45"
        );
        return record;
    }

record DataResponse45(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/46")
    public DataResponse46 getData46(@RequestParam(required = false) String filter) {
        var record = new DataResponse46(
            UUID.randomUUID().toString(),
            "item-46",
            Instant.now(),
            46,
            "category-6",
            "description for record 46"
        );
        return record;
    }

record DataResponse46(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/47")
    public DataResponse47 getData47(@RequestParam(required = false) String filter) {
        var record = new DataResponse47(
            UUID.randomUUID().toString(),
            "item-47",
            Instant.now(),
            47,
            "category-7",
            "description for record 47"
        );
        return record;
    }

record DataResponse47(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/48")
    public DataResponse48 getData48(@RequestParam(required = false) String filter) {
        var record = new DataResponse48(
            UUID.randomUUID().toString(),
            "item-48",
            Instant.now(),
            48,
            "category-8",
            "description for record 48"
        );
        return record;
    }

record DataResponse48(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/49")
    public DataResponse49 getData49(@RequestParam(required = false) String filter) {
        var record = new DataResponse49(
            UUID.randomUUID().toString(),
            "item-49",
            Instant.now(),
            49,
            "category-9",
            "description for record 49"
        );
        return record;
    }

record DataResponse49(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/50")
    public DataResponse50 getData50(@RequestParam(required = false) String filter) {
        var record = new DataResponse50(
            UUID.randomUUID().toString(),
            "item-50",
            Instant.now(),
            50,
            "category-0",
            "description for record 50"
        );
        return record;
    }

record DataResponse50(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/51")
    public DataResponse51 getData51(@RequestParam(required = false) String filter) {
        var record = new DataResponse51(
            UUID.randomUUID().toString(),
            "item-51",
            Instant.now(),
            51,
            "category-1",
            "description for record 51"
        );
        return record;
    }

record DataResponse51(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/52")
    public DataResponse52 getData52(@RequestParam(required = false) String filter) {
        var record = new DataResponse52(
            UUID.randomUUID().toString(),
            "item-52",
            Instant.now(),
            52,
            "category-2",
            "description for record 52"
        );
        return record;
    }

record DataResponse52(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/53")
    public DataResponse53 getData53(@RequestParam(required = false) String filter) {
        var record = new DataResponse53(
            UUID.randomUUID().toString(),
            "item-53",
            Instant.now(),
            53,
            "category-3",
            "description for record 53"
        );
        return record;
    }

record DataResponse53(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/54")
    public DataResponse54 getData54(@RequestParam(required = false) String filter) {
        var record = new DataResponse54(
            UUID.randomUUID().toString(),
            "item-54",
            Instant.now(),
            54,
            "category-4",
            "description for record 54"
        );
        return record;
    }

record DataResponse54(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/55")
    public DataResponse55 getData55(@RequestParam(required = false) String filter) {
        var record = new DataResponse55(
            UUID.randomUUID().toString(),
            "item-55",
            Instant.now(),
            55,
            "category-5",
            "description for record 55"
        );
        return record;
    }

record DataResponse55(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/56")
    public DataResponse56 getData56(@RequestParam(required = false) String filter) {
        var record = new DataResponse56(
            UUID.randomUUID().toString(),
            "item-56",
            Instant.now(),
            56,
            "category-6",
            "description for record 56"
        );
        return record;
    }

record DataResponse56(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/57")
    public DataResponse57 getData57(@RequestParam(required = false) String filter) {
        var record = new DataResponse57(
            UUID.randomUUID().toString(),
            "item-57",
            Instant.now(),
            57,
            "category-7",
            "description for record 57"
        );
        return record;
    }

record DataResponse57(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/58")
    public DataResponse58 getData58(@RequestParam(required = false) String filter) {
        var record = new DataResponse58(
            UUID.randomUUID().toString(),
            "item-58",
            Instant.now(),
            58,
            "category-8",
            "description for record 58"
        );
        return record;
    }

record DataResponse58(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/59")
    public DataResponse59 getData59(@RequestParam(required = false) String filter) {
        var record = new DataResponse59(
            UUID.randomUUID().toString(),
            "item-59",
            Instant.now(),
            59,
            "category-9",
            "description for record 59"
        );
        return record;
    }

record DataResponse59(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/60")
    public DataResponse60 getData60(@RequestParam(required = false) String filter) {
        var record = new DataResponse60(
            UUID.randomUUID().toString(),
            "item-60",
            Instant.now(),
            60,
            "category-0",
            "description for record 60"
        );
        return record;
    }

record DataResponse60(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/61")
    public DataResponse61 getData61(@RequestParam(required = false) String filter) {
        var record = new DataResponse61(
            UUID.randomUUID().toString(),
            "item-61",
            Instant.now(),
            61,
            "category-1",
            "description for record 61"
        );
        return record;
    }

record DataResponse61(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/62")
    public DataResponse62 getData62(@RequestParam(required = false) String filter) {
        var record = new DataResponse62(
            UUID.randomUUID().toString(),
            "item-62",
            Instant.now(),
            62,
            "category-2",
            "description for record 62"
        );
        return record;
    }

record DataResponse62(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/63")
    public DataResponse63 getData63(@RequestParam(required = false) String filter) {
        var record = new DataResponse63(
            UUID.randomUUID().toString(),
            "item-63",
            Instant.now(),
            63,
            "category-3",
            "description for record 63"
        );
        return record;
    }

record DataResponse63(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/64")
    public DataResponse64 getData64(@RequestParam(required = false) String filter) {
        var record = new DataResponse64(
            UUID.randomUUID().toString(),
            "item-64",
            Instant.now(),
            64,
            "category-4",
            "description for record 64"
        );
        return record;
    }

record DataResponse64(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/65")
    public DataResponse65 getData65(@RequestParam(required = false) String filter) {
        var record = new DataResponse65(
            UUID.randomUUID().toString(),
            "item-65",
            Instant.now(),
            65,
            "category-5",
            "description for record 65"
        );
        return record;
    }

record DataResponse65(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/66")
    public DataResponse66 getData66(@RequestParam(required = false) String filter) {
        var record = new DataResponse66(
            UUID.randomUUID().toString(),
            "item-66",
            Instant.now(),
            66,
            "category-6",
            "description for record 66"
        );
        return record;
    }

record DataResponse66(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/67")
    public DataResponse67 getData67(@RequestParam(required = false) String filter) {
        var record = new DataResponse67(
            UUID.randomUUID().toString(),
            "item-67",
            Instant.now(),
            67,
            "category-7",
            "description for record 67"
        );
        return record;
    }

record DataResponse67(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/68")
    public DataResponse68 getData68(@RequestParam(required = false) String filter) {
        var record = new DataResponse68(
            UUID.randomUUID().toString(),
            "item-68",
            Instant.now(),
            68,
            "category-8",
            "description for record 68"
        );
        return record;
    }

record DataResponse68(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/69")
    public DataResponse69 getData69(@RequestParam(required = false) String filter) {
        var record = new DataResponse69(
            UUID.randomUUID().toString(),
            "item-69",
            Instant.now(),
            69,
            "category-9",
            "description for record 69"
        );
        return record;
    }

record DataResponse69(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/70")
    public DataResponse70 getData70(@RequestParam(required = false) String filter) {
        var record = new DataResponse70(
            UUID.randomUUID().toString(),
            "item-70",
            Instant.now(),
            70,
            "category-0",
            "description for record 70"
        );
        return record;
    }

record DataResponse70(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/71")
    public DataResponse71 getData71(@RequestParam(required = false) String filter) {
        var record = new DataResponse71(
            UUID.randomUUID().toString(),
            "item-71",
            Instant.now(),
            71,
            "category-1",
            "description for record 71"
        );
        return record;
    }

record DataResponse71(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/72")
    public DataResponse72 getData72(@RequestParam(required = false) String filter) {
        var record = new DataResponse72(
            UUID.randomUUID().toString(),
            "item-72",
            Instant.now(),
            72,
            "category-2",
            "description for record 72"
        );
        return record;
    }

record DataResponse72(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/73")
    public DataResponse73 getData73(@RequestParam(required = false) String filter) {
        var record = new DataResponse73(
            UUID.randomUUID().toString(),
            "item-73",
            Instant.now(),
            73,
            "category-3",
            "description for record 73"
        );
        return record;
    }

record DataResponse73(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/74")
    public DataResponse74 getData74(@RequestParam(required = false) String filter) {
        var record = new DataResponse74(
            UUID.randomUUID().toString(),
            "item-74",
            Instant.now(),
            74,
            "category-4",
            "description for record 74"
        );
        return record;
    }

record DataResponse74(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/75")
    public DataResponse75 getData75(@RequestParam(required = false) String filter) {
        var record = new DataResponse75(
            UUID.randomUUID().toString(),
            "item-75",
            Instant.now(),
            75,
            "category-5",
            "description for record 75"
        );
        return record;
    }

record DataResponse75(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/76")
    public DataResponse76 getData76(@RequestParam(required = false) String filter) {
        var record = new DataResponse76(
            UUID.randomUUID().toString(),
            "item-76",
            Instant.now(),
            76,
            "category-6",
            "description for record 76"
        );
        return record;
    }

record DataResponse76(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/77")
    public DataResponse77 getData77(@RequestParam(required = false) String filter) {
        var record = new DataResponse77(
            UUID.randomUUID().toString(),
            "item-77",
            Instant.now(),
            77,
            "category-7",
            "description for record 77"
        );
        return record;
    }

record DataResponse77(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/78")
    public DataResponse78 getData78(@RequestParam(required = false) String filter) {
        var record = new DataResponse78(
            UUID.randomUUID().toString(),
            "item-78",
            Instant.now(),
            78,
            "category-8",
            "description for record 78"
        );
        return record;
    }

record DataResponse78(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/79")
    public DataResponse79 getData79(@RequestParam(required = false) String filter) {
        var record = new DataResponse79(
            UUID.randomUUID().toString(),
            "item-79",
            Instant.now(),
            79,
            "category-9",
            "description for record 79"
        );
        return record;
    }

record DataResponse79(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/80")
    public DataResponse80 getData80(@RequestParam(required = false) String filter) {
        var record = new DataResponse80(
            UUID.randomUUID().toString(),
            "item-80",
            Instant.now(),
            80,
            "category-0",
            "description for record 80"
        );
        return record;
    }

record DataResponse80(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/81")
    public DataResponse81 getData81(@RequestParam(required = false) String filter) {
        var record = new DataResponse81(
            UUID.randomUUID().toString(),
            "item-81",
            Instant.now(),
            81,
            "category-1",
            "description for record 81"
        );
        return record;
    }

record DataResponse81(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/82")
    public DataResponse82 getData82(@RequestParam(required = false) String filter) {
        var record = new DataResponse82(
            UUID.randomUUID().toString(),
            "item-82",
            Instant.now(),
            82,
            "category-2",
            "description for record 82"
        );
        return record;
    }

record DataResponse82(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/83")
    public DataResponse83 getData83(@RequestParam(required = false) String filter) {
        var record = new DataResponse83(
            UUID.randomUUID().toString(),
            "item-83",
            Instant.now(),
            83,
            "category-3",
            "description for record 83"
        );
        return record;
    }

record DataResponse83(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/84")
    public DataResponse84 getData84(@RequestParam(required = false) String filter) {
        var record = new DataResponse84(
            UUID.randomUUID().toString(),
            "item-84",
            Instant.now(),
            84,
            "category-4",
            "description for record 84"
        );
        return record;
    }

record DataResponse84(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/85")
    public DataResponse85 getData85(@RequestParam(required = false) String filter) {
        var record = new DataResponse85(
            UUID.randomUUID().toString(),
            "item-85",
            Instant.now(),
            85,
            "category-5",
            "description for record 85"
        );
        return record;
    }

record DataResponse85(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/86")
    public DataResponse86 getData86(@RequestParam(required = false) String filter) {
        var record = new DataResponse86(
            UUID.randomUUID().toString(),
            "item-86",
            Instant.now(),
            86,
            "category-6",
            "description for record 86"
        );
        return record;
    }

record DataResponse86(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/87")
    public DataResponse87 getData87(@RequestParam(required = false) String filter) {
        var record = new DataResponse87(
            UUID.randomUUID().toString(),
            "item-87",
            Instant.now(),
            87,
            "category-7",
            "description for record 87"
        );
        return record;
    }

record DataResponse87(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/88")
    public DataResponse88 getData88(@RequestParam(required = false) String filter) {
        var record = new DataResponse88(
            UUID.randomUUID().toString(),
            "item-88",
            Instant.now(),
            88,
            "category-8",
            "description for record 88"
        );
        return record;
    }

record DataResponse88(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/89")
    public DataResponse89 getData89(@RequestParam(required = false) String filter) {
        var record = new DataResponse89(
            UUID.randomUUID().toString(),
            "item-89",
            Instant.now(),
            89,
            "category-9",
            "description for record 89"
        );
        return record;
    }

record DataResponse89(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/90")
    public DataResponse90 getData90(@RequestParam(required = false) String filter) {
        var record = new DataResponse90(
            UUID.randomUUID().toString(),
            "item-90",
            Instant.now(),
            90,
            "category-0",
            "description for record 90"
        );
        return record;
    }

record DataResponse90(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/91")
    public DataResponse91 getData91(@RequestParam(required = false) String filter) {
        var record = new DataResponse91(
            UUID.randomUUID().toString(),
            "item-91",
            Instant.now(),
            91,
            "category-1",
            "description for record 91"
        );
        return record;
    }

record DataResponse91(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/92")
    public DataResponse92 getData92(@RequestParam(required = false) String filter) {
        var record = new DataResponse92(
            UUID.randomUUID().toString(),
            "item-92",
            Instant.now(),
            92,
            "category-2",
            "description for record 92"
        );
        return record;
    }

record DataResponse92(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/93")
    public DataResponse93 getData93(@RequestParam(required = false) String filter) {
        var record = new DataResponse93(
            UUID.randomUUID().toString(),
            "item-93",
            Instant.now(),
            93,
            "category-3",
            "description for record 93"
        );
        return record;
    }

record DataResponse93(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/94")
    public DataResponse94 getData94(@RequestParam(required = false) String filter) {
        var record = new DataResponse94(
            UUID.randomUUID().toString(),
            "item-94",
            Instant.now(),
            94,
            "category-4",
            "description for record 94"
        );
        return record;
    }

record DataResponse94(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/95")
    public DataResponse95 getData95(@RequestParam(required = false) String filter) {
        var record = new DataResponse95(
            UUID.randomUUID().toString(),
            "item-95",
            Instant.now(),
            95,
            "category-5",
            "description for record 95"
        );
        return record;
    }

record DataResponse95(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/96")
    public DataResponse96 getData96(@RequestParam(required = false) String filter) {
        var record = new DataResponse96(
            UUID.randomUUID().toString(),
            "item-96",
            Instant.now(),
            96,
            "category-6",
            "description for record 96"
        );
        return record;
    }

record DataResponse96(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/97")
    public DataResponse97 getData97(@RequestParam(required = false) String filter) {
        var record = new DataResponse97(
            UUID.randomUUID().toString(),
            "item-97",
            Instant.now(),
            97,
            "category-7",
            "description for record 97"
        );
        return record;
    }

record DataResponse97(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/98")
    public DataResponse98 getData98(@RequestParam(required = false) String filter) {
        var record = new DataResponse98(
            UUID.randomUUID().toString(),
            "item-98",
            Instant.now(),
            98,
            "category-8",
            "description for record 98"
        );
        return record;
    }

record DataResponse98(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/99")
    public DataResponse99 getData99(@RequestParam(required = false) String filter) {
        var record = new DataResponse99(
            UUID.randomUUID().toString(),
            "item-99",
            Instant.now(),
            99,
            "category-9",
            "description for record 99"
        );
        return record;
    }

record DataResponse99(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/100")
    public DataResponse100 getData100(@RequestParam(required = false) String filter) {
        var record = new DataResponse100(
            UUID.randomUUID().toString(),
            "item-100",
            Instant.now(),
            100,
            "category-0",
            "description for record 100"
        );
        return record;
    }

record DataResponse100(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/101")
    public DataResponse101 getData101(@RequestParam(required = false) String filter) {
        var record = new DataResponse101(
            UUID.randomUUID().toString(),
            "item-101",
            Instant.now(),
            101,
            "category-1",
            "description for record 101"
        );
        return record;
    }

record DataResponse101(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/102")
    public DataResponse102 getData102(@RequestParam(required = false) String filter) {
        var record = new DataResponse102(
            UUID.randomUUID().toString(),
            "item-102",
            Instant.now(),
            102,
            "category-2",
            "description for record 102"
        );
        return record;
    }

record DataResponse102(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/103")
    public DataResponse103 getData103(@RequestParam(required = false) String filter) {
        var record = new DataResponse103(
            UUID.randomUUID().toString(),
            "item-103",
            Instant.now(),
            103,
            "category-3",
            "description for record 103"
        );
        return record;
    }

record DataResponse103(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/104")
    public DataResponse104 getData104(@RequestParam(required = false) String filter) {
        var record = new DataResponse104(
            UUID.randomUUID().toString(),
            "item-104",
            Instant.now(),
            104,
            "category-4",
            "description for record 104"
        );
        return record;
    }

record DataResponse104(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/105")
    public DataResponse105 getData105(@RequestParam(required = false) String filter) {
        var record = new DataResponse105(
            UUID.randomUUID().toString(),
            "item-105",
            Instant.now(),
            105,
            "category-5",
            "description for record 105"
        );
        return record;
    }

record DataResponse105(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/106")
    public DataResponse106 getData106(@RequestParam(required = false) String filter) {
        var record = new DataResponse106(
            UUID.randomUUID().toString(),
            "item-106",
            Instant.now(),
            106,
            "category-6",
            "description for record 106"
        );
        return record;
    }

record DataResponse106(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/107")
    public DataResponse107 getData107(@RequestParam(required = false) String filter) {
        var record = new DataResponse107(
            UUID.randomUUID().toString(),
            "item-107",
            Instant.now(),
            107,
            "category-7",
            "description for record 107"
        );
        return record;
    }

record DataResponse107(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/108")
    public DataResponse108 getData108(@RequestParam(required = false) String filter) {
        var record = new DataResponse108(
            UUID.randomUUID().toString(),
            "item-108",
            Instant.now(),
            108,
            "category-8",
            "description for record 108"
        );
        return record;
    }

record DataResponse108(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/109")
    public DataResponse109 getData109(@RequestParam(required = false) String filter) {
        var record = new DataResponse109(
            UUID.randomUUID().toString(),
            "item-109",
            Instant.now(),
            109,
            "category-9",
            "description for record 109"
        );
        return record;
    }

record DataResponse109(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/110")
    public DataResponse110 getData110(@RequestParam(required = false) String filter) {
        var record = new DataResponse110(
            UUID.randomUUID().toString(),
            "item-110",
            Instant.now(),
            110,
            "category-0",
            "description for record 110"
        );
        return record;
    }

record DataResponse110(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/111")
    public DataResponse111 getData111(@RequestParam(required = false) String filter) {
        var record = new DataResponse111(
            UUID.randomUUID().toString(),
            "item-111",
            Instant.now(),
            111,
            "category-1",
            "description for record 111"
        );
        return record;
    }

record DataResponse111(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/112")
    public DataResponse112 getData112(@RequestParam(required = false) String filter) {
        var record = new DataResponse112(
            UUID.randomUUID().toString(),
            "item-112",
            Instant.now(),
            112,
            "category-2",
            "description for record 112"
        );
        return record;
    }

record DataResponse112(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/113")
    public DataResponse113 getData113(@RequestParam(required = false) String filter) {
        var record = new DataResponse113(
            UUID.randomUUID().toString(),
            "item-113",
            Instant.now(),
            113,
            "category-3",
            "description for record 113"
        );
        return record;
    }

record DataResponse113(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/114")
    public DataResponse114 getData114(@RequestParam(required = false) String filter) {
        var record = new DataResponse114(
            UUID.randomUUID().toString(),
            "item-114",
            Instant.now(),
            114,
            "category-4",
            "description for record 114"
        );
        return record;
    }

record DataResponse114(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/115")
    public DataResponse115 getData115(@RequestParam(required = false) String filter) {
        var record = new DataResponse115(
            UUID.randomUUID().toString(),
            "item-115",
            Instant.now(),
            115,
            "category-5",
            "description for record 115"
        );
        return record;
    }

record DataResponse115(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/116")
    public DataResponse116 getData116(@RequestParam(required = false) String filter) {
        var record = new DataResponse116(
            UUID.randomUUID().toString(),
            "item-116",
            Instant.now(),
            116,
            "category-6",
            "description for record 116"
        );
        return record;
    }

record DataResponse116(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/117")
    public DataResponse117 getData117(@RequestParam(required = false) String filter) {
        var record = new DataResponse117(
            UUID.randomUUID().toString(),
            "item-117",
            Instant.now(),
            117,
            "category-7",
            "description for record 117"
        );
        return record;
    }

record DataResponse117(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/118")
    public DataResponse118 getData118(@RequestParam(required = false) String filter) {
        var record = new DataResponse118(
            UUID.randomUUID().toString(),
            "item-118",
            Instant.now(),
            118,
            "category-8",
            "description for record 118"
        );
        return record;
    }

record DataResponse118(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/119")
    public DataResponse119 getData119(@RequestParam(required = false) String filter) {
        var record = new DataResponse119(
            UUID.randomUUID().toString(),
            "item-119",
            Instant.now(),
            119,
            "category-9",
            "description for record 119"
        );
        return record;
    }

record DataResponse119(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/120")
    public DataResponse120 getData120(@RequestParam(required = false) String filter) {
        var record = new DataResponse120(
            UUID.randomUUID().toString(),
            "item-120",
            Instant.now(),
            120,
            "category-0",
            "description for record 120"
        );
        return record;
    }

record DataResponse120(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/121")
    public DataResponse121 getData121(@RequestParam(required = false) String filter) {
        var record = new DataResponse121(
            UUID.randomUUID().toString(),
            "item-121",
            Instant.now(),
            121,
            "category-1",
            "description for record 121"
        );
        return record;
    }

record DataResponse121(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/122")
    public DataResponse122 getData122(@RequestParam(required = false) String filter) {
        var record = new DataResponse122(
            UUID.randomUUID().toString(),
            "item-122",
            Instant.now(),
            122,
            "category-2",
            "description for record 122"
        );
        return record;
    }

record DataResponse122(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/123")
    public DataResponse123 getData123(@RequestParam(required = false) String filter) {
        var record = new DataResponse123(
            UUID.randomUUID().toString(),
            "item-123",
            Instant.now(),
            123,
            "category-3",
            "description for record 123"
        );
        return record;
    }

record DataResponse123(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/124")
    public DataResponse124 getData124(@RequestParam(required = false) String filter) {
        var record = new DataResponse124(
            UUID.randomUUID().toString(),
            "item-124",
            Instant.now(),
            124,
            "category-4",
            "description for record 124"
        );
        return record;
    }

record DataResponse124(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/125")
    public DataResponse125 getData125(@RequestParam(required = false) String filter) {
        var record = new DataResponse125(
            UUID.randomUUID().toString(),
            "item-125",
            Instant.now(),
            125,
            "category-5",
            "description for record 125"
        );
        return record;
    }

record DataResponse125(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/126")
    public DataResponse126 getData126(@RequestParam(required = false) String filter) {
        var record = new DataResponse126(
            UUID.randomUUID().toString(),
            "item-126",
            Instant.now(),
            126,
            "category-6",
            "description for record 126"
        );
        return record;
    }

record DataResponse126(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/127")
    public DataResponse127 getData127(@RequestParam(required = false) String filter) {
        var record = new DataResponse127(
            UUID.randomUUID().toString(),
            "item-127",
            Instant.now(),
            127,
            "category-7",
            "description for record 127"
        );
        return record;
    }

record DataResponse127(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/128")
    public DataResponse128 getData128(@RequestParam(required = false) String filter) {
        var record = new DataResponse128(
            UUID.randomUUID().toString(),
            "item-128",
            Instant.now(),
            128,
            "category-8",
            "description for record 128"
        );
        return record;
    }

record DataResponse128(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/129")
    public DataResponse129 getData129(@RequestParam(required = false) String filter) {
        var record = new DataResponse129(
            UUID.randomUUID().toString(),
            "item-129",
            Instant.now(),
            129,
            "category-9",
            "description for record 129"
        );
        return record;
    }

record DataResponse129(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/130")
    public DataResponse130 getData130(@RequestParam(required = false) String filter) {
        var record = new DataResponse130(
            UUID.randomUUID().toString(),
            "item-130",
            Instant.now(),
            130,
            "category-0",
            "description for record 130"
        );
        return record;
    }

record DataResponse130(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/131")
    public DataResponse131 getData131(@RequestParam(required = false) String filter) {
        var record = new DataResponse131(
            UUID.randomUUID().toString(),
            "item-131",
            Instant.now(),
            131,
            "category-1",
            "description for record 131"
        );
        return record;
    }

record DataResponse131(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/132")
    public DataResponse132 getData132(@RequestParam(required = false) String filter) {
        var record = new DataResponse132(
            UUID.randomUUID().toString(),
            "item-132",
            Instant.now(),
            132,
            "category-2",
            "description for record 132"
        );
        return record;
    }

record DataResponse132(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/133")
    public DataResponse133 getData133(@RequestParam(required = false) String filter) {
        var record = new DataResponse133(
            UUID.randomUUID().toString(),
            "item-133",
            Instant.now(),
            133,
            "category-3",
            "description for record 133"
        );
        return record;
    }

record DataResponse133(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/134")
    public DataResponse134 getData134(@RequestParam(required = false) String filter) {
        var record = new DataResponse134(
            UUID.randomUUID().toString(),
            "item-134",
            Instant.now(),
            134,
            "category-4",
            "description for record 134"
        );
        return record;
    }

record DataResponse134(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/135")
    public DataResponse135 getData135(@RequestParam(required = false) String filter) {
        var record = new DataResponse135(
            UUID.randomUUID().toString(),
            "item-135",
            Instant.now(),
            135,
            "category-5",
            "description for record 135"
        );
        return record;
    }

record DataResponse135(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/136")
    public DataResponse136 getData136(@RequestParam(required = false) String filter) {
        var record = new DataResponse136(
            UUID.randomUUID().toString(),
            "item-136",
            Instant.now(),
            136,
            "category-6",
            "description for record 136"
        );
        return record;
    }

record DataResponse136(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/137")
    public DataResponse137 getData137(@RequestParam(required = false) String filter) {
        var record = new DataResponse137(
            UUID.randomUUID().toString(),
            "item-137",
            Instant.now(),
            137,
            "category-7",
            "description for record 137"
        );
        return record;
    }

record DataResponse137(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/138")
    public DataResponse138 getData138(@RequestParam(required = false) String filter) {
        var record = new DataResponse138(
            UUID.randomUUID().toString(),
            "item-138",
            Instant.now(),
            138,
            "category-8",
            "description for record 138"
        );
        return record;
    }

record DataResponse138(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/139")
    public DataResponse139 getData139(@RequestParam(required = false) String filter) {
        var record = new DataResponse139(
            UUID.randomUUID().toString(),
            "item-139",
            Instant.now(),
            139,
            "category-9",
            "description for record 139"
        );
        return record;
    }

record DataResponse139(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/140")
    public DataResponse140 getData140(@RequestParam(required = false) String filter) {
        var record = new DataResponse140(
            UUID.randomUUID().toString(),
            "item-140",
            Instant.now(),
            140,
            "category-0",
            "description for record 140"
        );
        return record;
    }

record DataResponse140(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/141")
    public DataResponse141 getData141(@RequestParam(required = false) String filter) {
        var record = new DataResponse141(
            UUID.randomUUID().toString(),
            "item-141",
            Instant.now(),
            141,
            "category-1",
            "description for record 141"
        );
        return record;
    }

record DataResponse141(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/142")
    public DataResponse142 getData142(@RequestParam(required = false) String filter) {
        var record = new DataResponse142(
            UUID.randomUUID().toString(),
            "item-142",
            Instant.now(),
            142,
            "category-2",
            "description for record 142"
        );
        return record;
    }

record DataResponse142(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/143")
    public DataResponse143 getData143(@RequestParam(required = false) String filter) {
        var record = new DataResponse143(
            UUID.randomUUID().toString(),
            "item-143",
            Instant.now(),
            143,
            "category-3",
            "description for record 143"
        );
        return record;
    }

record DataResponse143(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/144")
    public DataResponse144 getData144(@RequestParam(required = false) String filter) {
        var record = new DataResponse144(
            UUID.randomUUID().toString(),
            "item-144",
            Instant.now(),
            144,
            "category-4",
            "description for record 144"
        );
        return record;
    }

record DataResponse144(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/145")
    public DataResponse145 getData145(@RequestParam(required = false) String filter) {
        var record = new DataResponse145(
            UUID.randomUUID().toString(),
            "item-145",
            Instant.now(),
            145,
            "category-5",
            "description for record 145"
        );
        return record;
    }

record DataResponse145(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/146")
    public DataResponse146 getData146(@RequestParam(required = false) String filter) {
        var record = new DataResponse146(
            UUID.randomUUID().toString(),
            "item-146",
            Instant.now(),
            146,
            "category-6",
            "description for record 146"
        );
        return record;
    }

record DataResponse146(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/147")
    public DataResponse147 getData147(@RequestParam(required = false) String filter) {
        var record = new DataResponse147(
            UUID.randomUUID().toString(),
            "item-147",
            Instant.now(),
            147,
            "category-7",
            "description for record 147"
        );
        return record;
    }

record DataResponse147(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/148")
    public DataResponse148 getData148(@RequestParam(required = false) String filter) {
        var record = new DataResponse148(
            UUID.randomUUID().toString(),
            "item-148",
            Instant.now(),
            148,
            "category-8",
            "description for record 148"
        );
        return record;
    }

record DataResponse148(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/149")
    public DataResponse149 getData149(@RequestParam(required = false) String filter) {
        var record = new DataResponse149(
            UUID.randomUUID().toString(),
            "item-149",
            Instant.now(),
            149,
            "category-9",
            "description for record 149"
        );
        return record;
    }

record DataResponse149(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/150")
    public DataResponse150 getData150(@RequestParam(required = false) String filter) {
        var record = new DataResponse150(
            UUID.randomUUID().toString(),
            "item-150",
            Instant.now(),
            150,
            "category-0",
            "description for record 150"
        );
        return record;
    }

record DataResponse150(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/151")
    public DataResponse151 getData151(@RequestParam(required = false) String filter) {
        var record = new DataResponse151(
            UUID.randomUUID().toString(),
            "item-151",
            Instant.now(),
            151,
            "category-1",
            "description for record 151"
        );
        return record;
    }

record DataResponse151(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/152")
    public DataResponse152 getData152(@RequestParam(required = false) String filter) {
        var record = new DataResponse152(
            UUID.randomUUID().toString(),
            "item-152",
            Instant.now(),
            152,
            "category-2",
            "description for record 152"
        );
        return record;
    }

record DataResponse152(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/153")
    public DataResponse153 getData153(@RequestParam(required = false) String filter) {
        var record = new DataResponse153(
            UUID.randomUUID().toString(),
            "item-153",
            Instant.now(),
            153,
            "category-3",
            "description for record 153"
        );
        return record;
    }

record DataResponse153(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/154")
    public DataResponse154 getData154(@RequestParam(required = false) String filter) {
        var record = new DataResponse154(
            UUID.randomUUID().toString(),
            "item-154",
            Instant.now(),
            154,
            "category-4",
            "description for record 154"
        );
        return record;
    }

record DataResponse154(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/155")
    public DataResponse155 getData155(@RequestParam(required = false) String filter) {
        var record = new DataResponse155(
            UUID.randomUUID().toString(),
            "item-155",
            Instant.now(),
            155,
            "category-5",
            "description for record 155"
        );
        return record;
    }

record DataResponse155(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/156")
    public DataResponse156 getData156(@RequestParam(required = false) String filter) {
        var record = new DataResponse156(
            UUID.randomUUID().toString(),
            "item-156",
            Instant.now(),
            156,
            "category-6",
            "description for record 156"
        );
        return record;
    }

record DataResponse156(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/157")
    public DataResponse157 getData157(@RequestParam(required = false) String filter) {
        var record = new DataResponse157(
            UUID.randomUUID().toString(),
            "item-157",
            Instant.now(),
            157,
            "category-7",
            "description for record 157"
        );
        return record;
    }

record DataResponse157(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/158")
    public DataResponse158 getData158(@RequestParam(required = false) String filter) {
        var record = new DataResponse158(
            UUID.randomUUID().toString(),
            "item-158",
            Instant.now(),
            158,
            "category-8",
            "description for record 158"
        );
        return record;
    }

record DataResponse158(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/159")
    public DataResponse159 getData159(@RequestParam(required = false) String filter) {
        var record = new DataResponse159(
            UUID.randomUUID().toString(),
            "item-159",
            Instant.now(),
            159,
            "category-9",
            "description for record 159"
        );
        return record;
    }

record DataResponse159(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/160")
    public DataResponse160 getData160(@RequestParam(required = false) String filter) {
        var record = new DataResponse160(
            UUID.randomUUID().toString(),
            "item-160",
            Instant.now(),
            160,
            "category-0",
            "description for record 160"
        );
        return record;
    }

record DataResponse160(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/161")
    public DataResponse161 getData161(@RequestParam(required = false) String filter) {
        var record = new DataResponse161(
            UUID.randomUUID().toString(),
            "item-161",
            Instant.now(),
            161,
            "category-1",
            "description for record 161"
        );
        return record;
    }

record DataResponse161(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/162")
    public DataResponse162 getData162(@RequestParam(required = false) String filter) {
        var record = new DataResponse162(
            UUID.randomUUID().toString(),
            "item-162",
            Instant.now(),
            162,
            "category-2",
            "description for record 162"
        );
        return record;
    }

record DataResponse162(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/163")
    public DataResponse163 getData163(@RequestParam(required = false) String filter) {
        var record = new DataResponse163(
            UUID.randomUUID().toString(),
            "item-163",
            Instant.now(),
            163,
            "category-3",
            "description for record 163"
        );
        return record;
    }

record DataResponse163(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/164")
    public DataResponse164 getData164(@RequestParam(required = false) String filter) {
        var record = new DataResponse164(
            UUID.randomUUID().toString(),
            "item-164",
            Instant.now(),
            164,
            "category-4",
            "description for record 164"
        );
        return record;
    }

record DataResponse164(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/165")
    public DataResponse165 getData165(@RequestParam(required = false) String filter) {
        var record = new DataResponse165(
            UUID.randomUUID().toString(),
            "item-165",
            Instant.now(),
            165,
            "category-5",
            "description for record 165"
        );
        return record;
    }

record DataResponse165(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/166")
    public DataResponse166 getData166(@RequestParam(required = false) String filter) {
        var record = new DataResponse166(
            UUID.randomUUID().toString(),
            "item-166",
            Instant.now(),
            166,
            "category-6",
            "description for record 166"
        );
        return record;
    }

record DataResponse166(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/167")
    public DataResponse167 getData167(@RequestParam(required = false) String filter) {
        var record = new DataResponse167(
            UUID.randomUUID().toString(),
            "item-167",
            Instant.now(),
            167,
            "category-7",
            "description for record 167"
        );
        return record;
    }

record DataResponse167(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/168")
    public DataResponse168 getData168(@RequestParam(required = false) String filter) {
        var record = new DataResponse168(
            UUID.randomUUID().toString(),
            "item-168",
            Instant.now(),
            168,
            "category-8",
            "description for record 168"
        );
        return record;
    }

record DataResponse168(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/169")
    public DataResponse169 getData169(@RequestParam(required = false) String filter) {
        var record = new DataResponse169(
            UUID.randomUUID().toString(),
            "item-169",
            Instant.now(),
            169,
            "category-9",
            "description for record 169"
        );
        return record;
    }

record DataResponse169(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/170")
    public DataResponse170 getData170(@RequestParam(required = false) String filter) {
        var record = new DataResponse170(
            UUID.randomUUID().toString(),
            "item-170",
            Instant.now(),
            170,
            "category-0",
            "description for record 170"
        );
        return record;
    }

record DataResponse170(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/171")
    public DataResponse171 getData171(@RequestParam(required = false) String filter) {
        var record = new DataResponse171(
            UUID.randomUUID().toString(),
            "item-171",
            Instant.now(),
            171,
            "category-1",
            "description for record 171"
        );
        return record;
    }

record DataResponse171(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/172")
    public DataResponse172 getData172(@RequestParam(required = false) String filter) {
        var record = new DataResponse172(
            UUID.randomUUID().toString(),
            "item-172",
            Instant.now(),
            172,
            "category-2",
            "description for record 172"
        );
        return record;
    }

record DataResponse172(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/173")
    public DataResponse173 getData173(@RequestParam(required = false) String filter) {
        var record = new DataResponse173(
            UUID.randomUUID().toString(),
            "item-173",
            Instant.now(),
            173,
            "category-3",
            "description for record 173"
        );
        return record;
    }

record DataResponse173(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/174")
    public DataResponse174 getData174(@RequestParam(required = false) String filter) {
        var record = new DataResponse174(
            UUID.randomUUID().toString(),
            "item-174",
            Instant.now(),
            174,
            "category-4",
            "description for record 174"
        );
        return record;
    }

record DataResponse174(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/175")
    public DataResponse175 getData175(@RequestParam(required = false) String filter) {
        var record = new DataResponse175(
            UUID.randomUUID().toString(),
            "item-175",
            Instant.now(),
            175,
            "category-5",
            "description for record 175"
        );
        return record;
    }

record DataResponse175(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/176")
    public DataResponse176 getData176(@RequestParam(required = false) String filter) {
        var record = new DataResponse176(
            UUID.randomUUID().toString(),
            "item-176",
            Instant.now(),
            176,
            "category-6",
            "description for record 176"
        );
        return record;
    }

record DataResponse176(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/177")
    public DataResponse177 getData177(@RequestParam(required = false) String filter) {
        var record = new DataResponse177(
            UUID.randomUUID().toString(),
            "item-177",
            Instant.now(),
            177,
            "category-7",
            "description for record 177"
        );
        return record;
    }

record DataResponse177(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/178")
    public DataResponse178 getData178(@RequestParam(required = false) String filter) {
        var record = new DataResponse178(
            UUID.randomUUID().toString(),
            "item-178",
            Instant.now(),
            178,
            "category-8",
            "description for record 178"
        );
        return record;
    }

record DataResponse178(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

    @GetMapping("/data/179")
    public DataResponse179 getData179(@RequestParam(required = false) String filter) {
        var record = new DataResponse179(
            UUID.randomUUID().toString(),
            "item-179",
            Instant.now(),
            179,
            "category-9",
            "description for record 179"
        );
        return record;
    }

record DataResponse179(
    String id,
    String name,
    Instant timestamp,
    int count,
    String category,
    String description
) {}

}
