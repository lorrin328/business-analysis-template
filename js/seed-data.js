// seed-data.js - local fallback data for offline/slow API startup
// ---------- Mock Data ----------
    const months = ['1月','2月','3月','4月','5月','6月','7月','8月','9月','10月','11月','12月'];

    const productData = {
      premium: [
        { value: 3520, name: '长期年金' },
        { value: 2800, name: '长期健康险' },
        { value: 2100, name: '短期险' },
        { value: 1850, name: '长期寿险' },
        { value: 1200, name: '万能/投连' },
        { value: 630, name: '其他' }
      ],
      count: [
        { value: 1200, name: '短期险' },
        { value: 850, name: '长期健康险' },
        { value: 620, name: '长期年金' },
        { value: 480, name: '长期寿险' },
        { value: 320, name: '万能/投连' },
        { value: 180, name: '其他' }
      ]
    };
    const productFilters = {
      transform: true,
      jingdai: true,
      transformLines: { 'OTO': true, '证保': true, '蚁桥': true },
      jingdaiOrgs: {},
      orgsInitialized: false
    };
    const productFallbackData = {
      "2026": {
        "transform:OTO": [
          {"name":"寿险","premium":6122.98,"count":2199},
          {"name":"年金","premium":2623.49,"count":451},
          {"name":"未分类","premium":56.92,"count":73},
          {"name":"短期险","premium":14.76,"count":222}
        ],
        "transform:证保": [
          {"name":"寿险","premium":1527.55,"count":222},
          {"name":"年金","premium":775.3,"count":42},
          {"name":"短期险","premium":0.11,"count":2}
        ],
        "transform:蚁桥": [
          {"name":"年金","premium":2730.9,"count":3258}
        ],
        "jingdai:支付宝-电商": [
          {"name":"4265e定盈互联网","premium":0,"count":6}
        ],
        "jingdai:蚂蚁保": [
          {"name":"7030e满利互联网","premium":17655.42,"count":368},
          {"name":"7043e满利2.0互联网","premium":2116.84,"count":79},
          {"name":"7032e百分年金互联网","premium":1906.06,"count":496},
          {"name":"7033e起领2.0互联网","premium":1679.88,"count":552},
          {"name":"7037e满多互联网","premium":777.22,"count":263},
          {"name":"7038e成长互联网","premium":653.92,"count":582},
          {"name":"7041利多多","premium":361.94,"count":65},
          {"name":"7031鑫多多2.0互联网","premium":292.73,"count":388},
          {"name":"4144专属商业养老-B账户","premium":160.34,"count":1023},
          {"name":"4265e定盈互联网","premium":83.83,"count":221},
          {"name":"4143专属商业养老-A账户","premium":9.06,"count":219},
          {"name":"7040e满分分红","premium":4.08,"count":16}
        ],
        "jingdai:京东保": [
          {"name":"7032e百分年金互联网","premium":28.36,"count":101},
          {"name":"7034e启航互联网","premium":16.9,"count":9},
          {"name":"7031鑫多多2.0互联网","premium":9.99,"count":97}
        ],
        "jingdai:微保": [
          {"name":"7032e百分年金互联网","premium":551.28,"count":439},
          {"name":"7035e百分2.0互联网","premium":136.73,"count":149},
          {"name":"7031鑫多多2.0互联网","premium":100.3,"count":182}
        ],
        "jingdai:招行网销": [
          {"name":"7031鑫多多2.0互联网","premium":1231.01,"count":436},
          {"name":"7032e百分年金互联网","premium":258.92,"count":148},
          {"name":"4143专属商业养老-A账户","premium":0.1,"count":1},
          {"name":"4144专属商业养老-B账户","premium":0.03,"count":1}
        ],
        "jingdai:慧择经纪": [
          {"name":"7031鑫多多2.0互联网","premium":122.46,"count":109},
          {"name":"7037e满多互联网","premium":2.67,"count":5},
          {"name":"4058荣耀金账户","premium":0,"count":3},
          {"name":"4059荣耀钻账户","premium":0,"count":1}
        ],
        "jingdai:经代自营": [
          {"name":"4144专属商业养老-B账户","premium":10,"count":71},
          {"name":"4248环球共享","premium":1.92,"count":3},
          {"name":"4143专属商业养老-A账户","premium":1.48,"count":28},
          {"name":"7017全球药械2022互联网","premium":0.14,"count":8}
        ]
      }
    };

    const teamMock = {
  "2024": {
    "headcount": {
      "OTO": [
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null
      ],
      "证保": [
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null
      ],
      "蚁桥": [
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null
      ]
    },
    "activeHeadcount": {
      "OTO": [
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null
      ],
      "证保": [
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null
      ],
      "蚁桥": [
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null
      ]
    },
    "premium": {
      "OTO": [
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null
      ],
      "证保": [
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null
      ],
      "蚁桥": [
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null
      ]
    }
  },
  "2025": {
    "headcount": {
      "OTO": [
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null
      ],
      "证保": [
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null
      ],
      "蚁桥": [
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null
      ]
    },
    "activeHeadcount": {
      "OTO": [
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null
      ],
      "证保": [
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null
      ],
      "蚁桥": [
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null
      ]
    },
    "premium": {
      "OTO": [
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null
      ],
      "证保": [
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null
      ],
      "蚁桥": [
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null
      ]
    }
  },
  "2026": {
    "headcount": {
      "OTO": [
        415,
        381,
        368,
        347,
        332,
        null,
        null,
        null,
        null,
        null,
        null,
        null
      ],
      "证保": [
        57,
        54,
        55,
        54,
        53,
        null,
        null,
        null,
        null,
        null,
        null,
        null
      ],
      "蚁桥": [
        60,
        63,
        64,
        65,
        67,
        null,
        null,
        null,
        null,
        null,
        null,
        null
      ]
    },
    "activeHeadcount": {
      "OTO": [
        286,
        113,
        161,
        186,
        22,
        null,
        null,
        null,
        null,
        null,
        null,
        null
      ],
      "证保": [
        32,
        13,
        21,
        24,
        2,
        null,
        null,
        null,
        null,
        null,
        null,
        null
      ],
      "蚁桥": [
        63,
        61,
        63,
        64,
        30,
        null,
        null,
        null,
        null,
        null,
        null,
        null
      ]
    },
    "premium": {
      "OTO": [
        5848.9,
        393.5,
        1606.5,
        901.7,
        67.6,
        null,
        null,
        null,
        null,
        null,
        null,
        null
      ],
      "证保": [
        1151.6,
        230.5,
        217.9,
        502.9,
        200.1,
        null,
        null,
        null,
        null,
        null,
        null,
        null
      ],
      "蚁桥": [
        818.6,
        528.0,
        868.4,
        504.0,
        11.9,
        null,
        null,
        null,
        null,
        null,
        null,
        null
      ]
    }
  }
};
